import json
import uuid
from datetime import UTC, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from py_vapid import Vapid02
from pywebpush import WebPushException, webpush
from rest_framework.exceptions import ValidationError

from .models import PushDelivery, PushSubscription, WorkerHeartbeat
from .outbox import push_payload
from .push_config import private_key, public_config, validate_endpoint


class NoRedirectSession(requests.Session):
    def post(self, url, *args, **kwargs):
        validate_endpoint(url)
        kwargs["allow_redirects"] = False
        return super().post(url, *args, **kwargs)


def send(subscription, notification):
    validate_endpoint(subscription.endpoint)
    headers = {}
    if urlsplit(subscription.endpoint).hostname.endswith(".notify.windows.com"):
        headers = {"X-WNS-Type": "wns/raw", "Content-Type": "application/octet-stream"}
    with NoRedirectSession() as session:
        return webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(push_payload(notification)),
            vapid_private_key=Vapid02(private_key()),
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            timeout=(3, settings.PUSH_HTTP_TIMEOUT_SECONDS),
            ttl=settings.PUSH_TTL_SECONDS,
            headers=headers,
            requests_session=session,
            verbose=False,
        )


@transaction.atomic
def claim():
    now = timezone.now()
    eligible = Q(state__in=["PENDIENTE", "REINTENTABLE"], next_attempt_at__lte=now) | Q(
        state="PROCESANDO", lease_until__lte=now
    )
    for _ in range(100):
        job = (
            PushDelivery.objects.select_for_update(skip_locked=True)
            .filter(eligible)
            .order_by("next_attempt_at", "id")
            .first()
        )
        if job is None:
            return None
        if job.attempts >= settings.PUSH_MAX_ATTEMPTS:
            job.state, job.last_error = "FALLIDO", "RETRY_LIMIT"
            job.lease_token, job.lease_until = None, None
            job.save()
            continue
        job.state = "PROCESANDO"
        job.attempts += 1
        job.lease_token = uuid.uuid4()
        job.lease_until = now + timedelta(seconds=settings.PUSH_LEASE_SECONDS)
        job.save()
        return job.id, job.lease_token
    return None


def retry_delay(value):
    if not value or len(str(value)) > 128:
        return 0
    try:
        seconds = int(value)
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            seconds = int((date - timezone.now()).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0
    return max(0, min(seconds, 86400))


@transaction.atomic
def complete(id, token, state, code="", *, retry_after=0, expired_subscription_at=None):
    job = PushDelivery.objects.select_for_update().get(pk=id)
    if job.state != "PROCESANDO" or job.lease_token != token or job.lease_until <= timezone.now():
        return False
    if state == "REINTENTABLE":
        if job.attempts >= settings.PUSH_MAX_ATTEMPTS:
            state = "FALLIDO"
        else:
            backoff = min(settings.PUSH_RETRY_BASE_SECONDS * 2 ** (job.attempts - 1), 3600)
            job.next_attempt_at = timezone.now() + timedelta(seconds=max(backoff, retry_after))
    if expired_subscription_at:
        PushSubscription.objects.filter(
            pk=job.subscription_id, updated_at=expired_subscription_at, active=True
        ).update(active=False, revoked_at=timezone.now(), updated_at=timezone.now())
    job.state, job.last_error = state, code
    job.lease_until, job.lease_token = None, None
    job.save()
    return True


def deliver(id, token, sender=None):
    job = PushDelivery.objects.select_related(
        "notification", "subscription__user", "subscription__device"
    ).get(pk=id)
    if job.state != "PROCESANDO" or job.lease_token != token or job.lease_until <= timezone.now():
        return False
    sub = job.subscription
    if (
        not sub.active
        or not sub.user.is_active
        or not sub.device.active
        or sub.user_id != job.notification.recipient_id
        or sub.device.user_id != sub.user_id
    ):
        return complete(id, token, "DESCARTADO", "SUBSCRIPTION_INACTIVE")
    try:
        response = (sender or send)(sub, job.notification)
        status, retry_after = response.status_code, response.headers.get("Retry-After")
    except WebPushException as exc:
        status, retry_after = exc.status_code, exc.retry_after
        if status is None:
            return complete(id, token, "FALLIDO", "INVALID_SUBSCRIPTION")
    except requests.RequestException:
        return complete(id, token, "REINTENTABLE", "NETWORK_ERROR")
    except (ValueError, ValidationError):
        return complete(id, token, "FALLIDO", "INVALID_CONFIGURATION_OR_SUBSCRIPTION")
    except Exception:
        # Provider exceptions can contain endpoints, keys and response bodies.
        return complete(id, token, "FALLIDO", "UNEXPECTED_ERROR")
    if 200 <= status < 300:
        return complete(id, token, "ACEPTADO_PROVEEDOR")
    if status in [404, 410]:
        return complete(
            id, token, "DESCARTADO", f"HTTP_{status}", expired_subscription_at=sub.updated_at
        )
    if status == 429 or status >= 500:
        return complete(
            id, token, "REINTENTABLE", f"HTTP_{status}", retry_after=retry_delay(retry_after)
        )
    return complete(id, token, "FALLIDO", f"HTTP_{status}")


def heartbeat(name):
    WorkerHeartbeat.objects.update_or_create(name=name, defaults={"seen_at": timezone.now()})


def run_once(*, worker_id="push-worker", limit=20):
    if not public_config()["enabled"]:
        raise ValueError("Web Push deshabilitado o configuración inválida.")
    count = 0
    heartbeat(worker_id)
    for _ in range(limit):
        claimed = claim()
        if not claimed:
            break
        deliver(*claimed)
        count += 1
        heartbeat(worker_id)
    return count
