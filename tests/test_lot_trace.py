from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.sync.models import SyncOperation
from apps.traceability.models import Conformity, Transfer, TransferLine, TransferVersion
from tests.test_access import assign
from tests.test_transfer_reads import client_for, transfer_fixture

pytestmark = pytest.mark.django_db


def test_admin_sees_origin_and_physical_journey_not_other_roles(user):
    transfer, lot, driver, receiver, _ = transfer_fixture(user)
    admin = User.objects.create_user(username="lot-admin", name="Administración")
    assign(admin, "ADMIN")
    pickup_at = timezone.now() - timedelta(hours=2)
    version = transfer.current_version
    version.published_at = pickup_at - timedelta(minutes=20)
    version.state = "PUBLICADA"
    version.save(update_fields=["published_at", "state"])
    operation = SyncOperation.objects.first()
    Conformity.objects.create(
        version=version, user=driver, stage="RECOGIDA", occurred_at=pickup_at, operation=operation
    )
    Conformity.objects.create(
        version=version,
        user=receiver,
        stage="RECEPCION",
        occurred_at=pickup_at + timedelta(minutes=45),
        operation=operation,
    )
    transfer.state = "RECIBIDO"
    transfer.save(update_fields=["state"])
    revised = TransferVersion.objects.create(
        transfer=transfer,
        number=2,
        origin=version.origin,
        destination=version.destination,
        emitter=user,
        driver=driver,
        receiver=receiver,
    )
    TransferLine.objects.create(
        version=revised,
        lot=lot,
        presentation=version.lines.get().presentation,
        units="5",
        content_base_snapshot="1",
        quantity="5",
    )
    revised.state = "PUBLICADA"
    revised.published_at = pickup_at + timedelta(hours=3)
    revised.save(update_fields=["state", "published_at"])
    transfer.current_version = revised
    transfer.save(update_fields=["current_version"])
    draft = Transfer.objects.create(code="T-draft", creator=user)
    draft_version = TransferVersion.objects.create(
        transfer=draft,
        number=1,
        origin=version.origin,
        destination=version.destination,
        emitter=user,
        driver=driver,
        receiver=receiver,
    )
    TransferLine.objects.create(
        version=draft_version,
        lot=lot,
        presentation=version.lines.get().presentation,
        units="1",
        content_base_snapshot="1",
        quantity="1",
    )
    draft.current_version = draft_version
    draft.save(update_fields=["current_version"])

    path = f"/api/v1/lots/{lot.id}/trace"
    assert client_for(user).get(path).status_code == 403
    assert client_for(driver).get(path).status_code == 403
    assert client_for(receiver).get(path).status_code == 403
    response = client_for(admin).get(path)
    assert response.status_code == 200
    data = response.json()
    assert data["lot"]["code"] == lot.code
    assert data["lot"]["responsible_name"] == user.name
    assert data["lot"]["quantity"] == "5.500"
    assert data["count"] == 1 and data["draft_count"] == 1 and data["next_offset"] is None
    journey = data["transfers"][0]
    assert journey["code"] == "T1" and journey["quantity"] == "5.000"
    assert journey["driver_name"] == "Driver" and journey["receiver_name"] == "Receiver"
    assert journey["pickup"]["actor_name"] == "Driver"
    assert journey["pickup"]["registered_at"]
    assert journey["travel_minutes"] == 45
    assert journey["has_history"] is True
    assert datetime.fromisoformat(journey["request_at"]) == version.published_at


def test_trace_branches_paginate_and_never_invent_negative_travel_time(user):
    transfer, lot, driver, receiver, _ = transfer_fixture(user)
    transfer.state = "PENDIENTE_RECOGIDA"
    transfer.save(update_fields=["state"])
    admin = User.objects.create_user(username="lot-admin")
    assign(admin, "ADMIN")
    second = Transfer.objects.create(code="T2", creator=user, state="CANCELADO")
    version = TransferVersion.objects.create(
        transfer=second,
        number=1,
        origin=transfer.current_version.origin,
        destination=transfer.current_version.destination,
        emitter=user,
        driver=driver,
        receiver=receiver,
    )
    TransferLine.objects.create(
        version=version,
        lot=lot,
        presentation=transfer.current_version.lines.get().presentation,
        units="1",
        content_base_snapshot="1",
        quantity="1",
    )
    second.current_version = version
    second.save(update_fields=["current_version"])
    operation = SyncOperation.objects.first()
    now = timezone.now()
    Conformity.objects.create(
        version=transfer.current_version,
        stage="RECOGIDA",
        user=driver,
        occurred_at=now,
        operation=operation,
    )
    Conformity.objects.create(
        version=transfer.current_version,
        stage="RECEPCION",
        user=receiver,
        occurred_at=now - timedelta(minutes=10),
        operation=operation,
    )
    client = client_for(admin)
    first = client.get(f"/api/v1/lots/{lot.id}/trace", {"limit": 1}).json()
    assert first["count"] == 2 and first["draft_count"] == 0 and first["next_offset"] == 1
    assert first["transfers"][0]["inconsistent_time"] is True
    assert first["transfers"][0]["travel_minutes"] is None
    second_page = client.get(f"/api/v1/lots/{lot.id}/trace", {"limit": 1, "offset": 1}).json()
    assert second_page["next_offset"] is None
    assert second_page["transfers"][0]["state"] == "CANCELADO"
    assert second_page["transfers"][0]["pickup"] is None
    assert client.get("/api/v1/lots", {"code": "NO-EXISTE"}).json()["count"] == 0
