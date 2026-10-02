import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
from django.db import connections, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.notifications.models import PushDelivery, PushSubscription
from apps.notifications.services import notify
from apps.notifications.worker import claim, complete, deliver, retry_delay, send
from tests.test_push_outbox import subscription
from tests.test_push_subscriptions import vapid  # noqa: F401

pytestmark = pytest.mark.django_db


def queued(user):
    subscription(user)
    with transaction.atomic():
        notify(
            recipients=[user.id],
            type="PICKUP_REQUESTED",
            source_event_id=uuid.uuid4(),
            entity_type="transfer",
            entity_id=uuid.uuid4(),
        )
    return PushDelivery.objects.get()


@pytest.mark.parametrize(
    "status,state",
    [
        (201, "ACEPTADO_PROVEEDOR"),
        (404, "DESCARTADO"),
        (410, "DESCARTADO"),
        (429, "REINTENTABLE"),
        (503, "REINTENTABLE"),
        (400, "FALLIDO"),
        (302, "FALLIDO"),
    ],
)
def test_provider_outcomes_preserve_inbox_and_disable_expired_endpoint(user, status, state):
    job = queued(user)
    id, token = claim()
    deliver(
        id,
        token,
        lambda sub, note: SimpleNamespace(status_code=status, headers={"Retry-After": "90"}),
    )
    job.refresh_from_db()
    assert job.state == state and job.notification.read_at is None
    assert job.subscription.active == (status not in [404, 410])
    if state == "REINTENTABLE":
        assert job.next_attempt_at > timezone.now() + timedelta(seconds=80)
        assert claim() is None
    else:
        assert claim() is None


def test_restart_recovers_lease_and_stale_worker_cannot_finish(user):
    job = queued(user)
    first = claim()
    PushDelivery.objects.filter(pk=job.id).update(lease_until=timezone.now() - timedelta(seconds=1))
    second = claim()
    assert first[1] != second[1]
    assert not complete(*first, "ACEPTADO_PROVEEDOR")
    assert complete(*second, "ACEPTADO_PROVEEDOR")
    job.refresh_from_db()
    assert job.attempts == 2 and claim() is None


def test_revoked_subscription_skips_network_and_errors_are_redacted(user, settings):
    job = queued(user)
    leased = claim()
    PushSubscription.objects.update(active=False)
    sender = Mock()
    deliver(*leased, sender=sender)
    sender.assert_not_called()
    job.refresh_from_db()
    assert job.state == "DESCARTADO"
    job.state, job.attempts = "PENDIENTE", 0
    job.save()
    PushSubscription.objects.update(active=True)
    settings.PUSH_MAX_ATTEMPTS = 1

    def unavailable(sub, note):
        raise requests.Timeout("sensitive endpoint and key")

    deliver(*claim(), sender=unavailable)
    job.refresh_from_db()
    assert job.state == "FALLIDO" and job.last_error == "NETWORK_ERROR"


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_two_workers_do_not_claim_the_same_delivery():
    user = User.objects.create_user(username="recipient")
    queued(user)
    barrier = Barrier(2)

    def run():
        try:
            barrier.wait(timeout=10)
            return claim()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run), pool.submit(run)]
        results = [future.result(timeout=15) for future in futures]
    assert sum(result is not None for result in results) == 1


@pytest.mark.usefixtures("vapid")
def test_sender_has_timeout_generic_payload_and_provider_specific_headers(user):
    job = queued(user)
    job.subscription.endpoint = "https://example.notify.windows.com/wpush/token"
    with patch(
        "apps.notifications.worker.webpush", return_value=SimpleNamespace(status_code=201)
    ) as provider:
        send(job.subscription, job.notification)
    kwargs = provider.call_args.kwargs
    assert kwargs["headers"]["X-WNS-Type"] == "wns/raw"
    assert kwargs["timeout"] == (3, 10)
    assert str(job.notification.entity_id) not in kwargs["data"]
    assert retry_delay("not a date") == 0
    assert retry_delay("999999") == 86400


@pytest.mark.usefixtures("vapid")
def test_worker_command_heartbeat_and_health(user):
    from io import StringIO

    from django.core.management import call_command
    from django.core.management.base import CommandError

    from apps.notifications.models import WorkerHeartbeat

    queued(user)
    output = StringIO()
    with patch(
        "apps.notifications.worker.send", return_value=SimpleNamespace(status_code=201, headers={})
    ):
        call_command("push_worker", once=True, worker_id="test", stdout=output)
    assert PushDelivery.objects.get().state == "ACEPTADO_PROVEEDOR"
    call_command("push_status", stdout=output)
    assert "last_heartbeat" in output.getvalue()
    WorkerHeartbeat.objects.update(seen_at=timezone.now() - timedelta(minutes=3))
    with pytest.raises(CommandError):
        call_command("push_status", stdout=StringIO())


def test_provider_redirects_are_not_followed():
    from apps.notifications.worker import NoRedirectSession

    with NoRedirectSession() as session, patch("requests.Session.post") as post:
        session.post("https://fcm.googleapis.com/fcm/send/token", allow_redirects=True)
    assert post.call_args.kwargs["allow_redirects"] is False
