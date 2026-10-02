import uuid

import pytest
from django.db import transaction

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import notify


def data(user):
    return dict(
        recipients=[user.id, user.id],
        type="PICKUP_REQUESTED",
        source_event_id=uuid.uuid4(),
        entity_type="transfer",
        entity_id=uuid.uuid4(),
    )


@pytest.mark.django_db
def test_notification_owner_read_and_dedup(api, user):
    args = data(user)
    with transaction.atomic():
        note = notify(**args)[0]
        assert notify(**args)[0].pk == note.pk
    stranger = User.objects.create_user(username="other")
    with transaction.atomic():
        other = notify(**{**data(stranger), "type": "RECEPTION_PENDING"})[0]
    body = api.get("/api/v1/notifications").json()
    assert body["count"] == body["unread_count"] == 1
    assert body["results"][0]["id"] == str(note.pk)
    assert api.post(f"/api/v1/notifications/{other.pk}/read", {}, format="json").status_code == 404
    result = api.post(f"/api/v1/notifications/{note.pk}/read", {}, format="json")
    assert result.status_code == 200
    assert (
        api.post(f"/api/v1/notifications/{note.pk}/read", {}, format="json").json()["read_at"]
        == result.json()["read_at"]
    )
    assert api.get("/api/v1/notifications").json()["unread_count"] == 0


@pytest.mark.django_db(transaction=True)
def test_notification_rollback_and_requires_atomic(user):
    with pytest.raises(RuntimeError):
        notify(**data(user))
    with pytest.raises(ValueError):
        with transaction.atomic():
            notify(**data(user))
            raise ValueError("business failed")
    assert not Notification.objects.exists()
