import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Location
from apps.common.errors import DomainError
from apps.sync.models import Device, SyncOperation
from apps.sync.services import execute, normalize

pytestmark = pytest.mark.django_db


def event(device, **overrides):
    value = {
        "event_id": str(uuid.uuid4()),
        "device_id": str(device.id),
        "type": "MILKING_CREATE",
        "entity_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "depends_on": [],
        "payload": {"value": "1.000"},
    }
    value.update(overrides)
    return value


def allow(actor, envelope):
    pass


def create_location(actor, envelope, operation):
    Location.objects.create(
        id=envelope["entity_id"], code=envelope["entity_id"].replace("-", ""), name="test", kind="CENTRO"
    )
    return {"lock_version": 1}


def test_register_is_owned_and_idempotent(api, user):
    device_id = str(uuid.uuid4())
    payload = {"id": device_id, "name": "Android"}
    assert api.post("/api/v1/devices", payload, format="json").status_code == 200
    assert api.post("/api/v1/devices", payload, format="json").status_code == 200
    assert Device.objects.count() == 1
    assert api.get("/api/v1/devices/current", HTTP_X_DEVICE_ID=device_id).status_code == 200
    other = User.objects.create_user(username="other")
    foreign = Device.objects.create(user=other, name="other")
    assert api.get("/api/v1/devices/current", HTTP_X_DEVICE_ID=str(foreign.id)).status_code == 403
    assert (
        api.post(
            "/api/v1/devices", {"id": str(foreign.id), "name": "steal"}, format="json"
        ).status_code
        == 403
    )
    assert (
        api.post("/api/v1/devices", {**payload, "user": str(other.id)}, format="json").status_code
        == 422
    )


def test_replay_hash_and_owner(user):
    device = Device.objects.create(user=user, name="test")
    command = event(device)
    first = execute(user, command, create_location, allow)
    assert execute(user, command, create_location, allow) == first
    assert Location.objects.count() == 1
    with pytest.raises(DomainError, match="UUID"):
        execute(user, {**command, "payload": {"value": "2.000"}}, create_location, allow)
    other = User.objects.create_user(username="other")
    other_device = Device.objects.create(user=other, name="other")
    with pytest.raises(DomainError):
        execute(other, {**command, "device_id": str(other_device.id)}, create_location, allow)
    assert SyncOperation.objects.count() == 1


def test_canonical_content_dependencies_and_rejection_are_stable(user):
    device = Device.objects.create(user=user, name="test")
    command = event(device)
    assert normalize(command)[1] == normalize(dict(reversed(list(command.items()))))[1]
    assert normalize(command)[1] != normalize({**command, "depends_on": [str(uuid.uuid4())]})[1]

    def reject(actor, envelope, operation):
        create_location(actor, envelope, operation)
        raise DomainError("INVALID_STATE", "Rejected")

    response, status = execute(user, command, reject, allow)
    assert status == 409 and response["status"] == "RECHAZADA"
    assert not Location.objects.exists()
    assert execute(user, command, create_location, allow) == (response, status)


def test_unknown_exception_rolls_back_receipt_and_business_change(user):
    device = Device.objects.create(user=user, name="test")
    command = event(device)

    def crash(actor, envelope, operation):
        create_location(actor, envelope, operation)
        raise RuntimeError("crash")

    with pytest.raises(RuntimeError):
        execute(user, command, crash, allow)
    assert not SyncOperation.objects.exists() and not Location.objects.exists()
    assert execute(user, command, create_location, allow)[0]["status"] == "APLICADA"


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_concurrent_duplicate_only_applies_once():
    user = User.objects.create_user(username="race")
    device = Device.objects.create(user=user, name="test")
    command = event(device)
    barrier = Barrier(2)

    def run():
        close_old_connections()
        try:
            actor = User.objects.get(pk=user.pk)
            barrier.wait(timeout=10)
            return execute(actor, command, create_location, allow)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert results[0] == results[1]
    assert SyncOperation.objects.count() == Location.objects.count() == 1
