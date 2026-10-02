import uuid

import pytest
from django.db import transaction

from apps.notifications.models import Notification, PushDelivery, PushSubscription
from apps.notifications.outbox import push_payload
from apps.notifications.services import EVENT_TYPES, notify
from apps.sync.models import Device

pytestmark = pytest.mark.django_db


def subscription(user, suffix="1", active=True):
    device = Device.objects.create(user=user, name=suffix)
    return PushSubscription.objects.create(
        user=user,
        device=device,
        endpoint=f"https://fcm.googleapis.com/fcm/send/{suffix}",
        p256dh="not-used-in-outbox-tests",
        auth="not-used",
        active=active,
    )


@pytest.mark.parametrize("type", sorted(EVENT_TYPES))
def test_all_notification_events_enqueue_once_per_active_subscription(user, type):
    subscription(user, "first")
    subscription(user, "second")
    subscription(user, "inactive", active=False)
    data = dict(
        recipients=[user.id, user.id],
        type=type,
        source_event_id=uuid.uuid4(),
        entity_type="transfer",
        entity_id=uuid.uuid4(),
    )
    with transaction.atomic():
        note = notify(**data)[0]
        notify(**data)
    assert Notification.objects.count() == 1 and PushDelivery.objects.count() == 2
    assert set(PushDelivery.objects.values_list("state", flat=True)) == {"PENDIENTE"}
    payload = push_payload(note)
    assert payload["tag"] == str(note.id) and str(note.entity_id) not in str(payload)
    assert "version_id" not in payload and "recipient_id" not in payload


def test_rollback_discards_internal_notification_and_push_jobs(user):
    subscription(user)
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            notify(
                recipients=[user.id],
                type="PICKUP_REQUESTED",
                source_event_id=uuid.uuid4(),
                entity_type="transfer",
                entity_id=uuid.uuid4(),
            )
            assert PushDelivery.objects.count() == 1
            raise RuntimeError("business failure after enqueue")
    assert not Notification.objects.exists() and not PushDelivery.objects.exists()
