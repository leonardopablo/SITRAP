import uuid
from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import RoleAssignment, User
from apps.sync.models import Device, SyncOperation
from tests.test_access import assign
from tests.test_auth import csrf, signin
from tests.test_sync_batch import chain
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db


def test_expired_session_does_not_consume_and_same_account_retries_original_uuid(user):
    create, _ = chain(user)
    client = APIClient(enforce_csrf_checks=True)
    signin(client)
    Session.objects.update(expire_date=timezone.now() - timedelta(seconds=1))
    result = client.post(
        "/api/v1/sync/events", {"events": [create]}, format="json", HTTP_X_CSRFTOKEN=csrf(client)
    )
    assert result.status_code == 401 and not SyncOperation.objects.exists()
    other = User.objects.create_user(username="another")
    assert (
        client_for(other)
        .post("/api/v1/sync/events", {"events": [create]}, format="json")
        .status_code
        == 403
    )
    assert not SyncOperation.objects.exists()
    signin(client)
    result = client.post(
        "/api/v1/sync/events", {"events": [create]}, format="json", HTTP_X_CSRFTOKEN=csrf(client)
    )
    assert (
        result.status_code == 200 and result.json()["results"][0]["event_id"] == create["event_id"]
    )
    assert result.json()["results"][0]["status"] == "APLICADA"


def test_permission_revocation_and_csrf_failures_leave_intention_retriable(user):
    create, _ = chain(user)
    client = APIClient(enforce_csrf_checks=True)
    signin(client)
    assert (
        client.post("/api/v1/sync/events", {"events": [create]}, format="json").status_code == 403
    )
    assert not SyncOperation.objects.exists()
    assignment = RoleAssignment.objects.get(user=user, role_id="PRODUCCION")
    center = assignment.location
    assignment.delete()
    result = client.post(
        "/api/v1/sync/events", {"events": [create]}, format="json", HTTP_X_CSRFTOKEN=csrf(client)
    )
    assert result.json()["results"][0]["status"] == "NO_PROCESADA"
    assert not SyncOperation.objects.exists()
    assign(user, "PRODUCCION", center)
    assert (
        client.post(
            "/api/v1/sync/events",
            {"events": [create]},
            format="json",
            HTTP_X_CSRFTOKEN=csrf(client),
        ).json()["results"][0]["status"]
        == "APLICADA"
    )


def test_preparation_expiry_is_distinct_from_session_and_preserves_old_work(user):
    create, _ = chain(user)
    device = Device.objects.get(pk=create["device_id"])
    device.prepared_at = timezone.now() - timedelta(days=8)
    device.preparation_expires_at = timezone.now() - timedelta(days=1)
    device.save()
    client = client_for(user)
    state = client.get("/api/v1/devices/current", HTTP_X_DEVICE_ID=str(device.id)).json()
    assert state["preparation_valid"] is False
    # The server still validates and accepts stored work after an online login.
    result = client.post("/api/v1/sync/events", {"events": [create]}, format="json")
    assert result.json()["results"][0]["status"] == "APLICADA"
    device.active = False
    device.save()
    create["event_id"] = str(uuid.uuid4())
    assert (
        client.post("/api/v1/sync/events", {"events": [create]}, format="json").status_code == 403
    )
    assert not SyncOperation.objects.filter(pk=create["event_id"]).exists()


def test_registering_device_does_not_extend_absolute_login_expiry(user):
    client = APIClient(enforce_csrf_checks=True)
    response = signin(client)
    assert response.json()["session_expires_at"]
    key = client.cookies["sessionid"].value
    expiration = Session.objects.get(pk=key).expire_date
    response = client.post(
        "/api/v1/devices",
        {"id": str(uuid.uuid4()), "name": "Personal"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf(client),
    )
    assert response.status_code == 200
    assert Session.objects.get(pk=key).expire_date == expiration


def test_batch_size_limits_reject_without_consuming_events(user, settings):
    create, _ = chain(user)
    client = client_for(user)
    assert client.post("/api/v1/sync/events", {"events": [create] * 101}, format="json").status_code == 422
    settings.SYNC_MAX_BATCH_BYTES = 100
    assert client.post("/api/v1/sync/events", {"events": [create]}, format="json").status_code == 422
    assert not SyncOperation.objects.exists()
