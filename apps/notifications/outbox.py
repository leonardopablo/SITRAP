from django.db import connection

from .models import PushDelivery, PushSubscription


def enqueue(notification):
    if not connection.in_atomic_block:
        raise RuntimeError("Push outbox must share the business transaction.")
    subscriptions = PushSubscription.objects.filter(
        user_id=notification.recipient_id,
        active=True,
        user__is_active=True,
        device__active=True,
        device__user_id=notification.recipient_id,
    )
    PushDelivery.objects.bulk_create(
        [
            PushDelivery(notification=notification, subscription_id=id)
            for id in subscriptions.values_list("id", flat=True)
        ],
        ignore_conflicts=True,
    )


def push_payload(notification):
    # Generic on purpose: the browser must authenticate and read current state.
    return {
        "notification_id": str(notification.id),
        "tag": str(notification.id),
        "title": "SITRAP",
        "body": "Tiene una actualización. Abra la aplicación.",
        "url": "/",
    }
