import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

import pytest
from django.db import IntegrityError, connections, transaction

from apps.accounts.models import User
from apps.common.errors import DomainError
from apps.milk.voiding import void_internal
from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.sync.models import Device
from apps.traceability.models import Conformity, Transfer
from tests.test_access import assign
from tests.test_transfer_draft import draft_command

pytestmark = pytest.mark.django_db


def send_command(command):
    return {
        **command,
        "event_id": str(uuid.uuid4()),
        "type": "TRANSFER_SEND",
        "expected_version": 1,
        "payload": {"version_id": command["payload"]["version_id"]},
    }


def test_send_atomic_replay_and_void_guard(api, user):
    command = draft_command(user)
    dispatch(user, command, fixed_type="TRANSFER_CREATE")
    send = send_command(command)
    path = f"/api/v1/transfers/{command['entity_id']}/send"
    result = api.post(path, send, format="json")
    assert result.status_code == 200, result.data
    assert api.post(path, send, format="json").json() == result.json()
    transfer = Transfer.objects.get(pk=command["entity_id"])
    assert transfer.state == "PENDIENTE_RECOGIDA"
    conformity = Conformity.objects.get(version=transfer.current_version)
    assert conformity.stage == "ENTREGA_ORIGEN"
    assert str(conformity.details.get().accepted_quantity) == "5.000"
    assert Notification.objects.filter(type="PICKUP_REQUESTED").count() == 1
    milking = transfer.current_version.lines.get().lot.production.milking
    with pytest.raises(DomainError, match="vinculada"):
        void_internal(user, milking.id, 2, "test")
    with pytest.raises(IntegrityError), transaction.atomic():
        transfer.current_version.lines.update(quantity="4")


def test_send_overallocation_and_notification_failure_rollback(user):
    command = draft_command(user)
    dispatch(user, command, fixed_type="TRANSFER_CREATE")
    with patch("apps.traceability.lifecycle.notify", side_effect=RuntimeError("fail")):
        with pytest.raises(RuntimeError):
            dispatch(user, send_command(command))
    transfer = Transfer.objects.get(pk=command["entity_id"])
    assert (
        transfer.state == "BORRADOR"
        and not Conformity.objects.filter(version__transfer=transfer).exists()
    )
    transfer.current_version.lines.update(quantity="6", units="6")
    result, status = dispatch(user, send_command(command))
    assert status == 409 and result["error"]["code"] == "ALLOCATION_EXCEEDED"
    assert not Notification.objects.exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_two_producers_cannot_overallocate():
    first = User.objects.create_user(username="first")
    one = draft_command(first)
    dispatch(first, one, fixed_type="TRANSFER_CREATE")
    second = User.objects.create_user(username="second")
    transfer = Transfer.objects.get(pk=one["entity_id"])
    assign(second, "PRODUCCION", transfer.current_version.origin)
    device = Device.objects.create(user=second, name="second")
    two = {
        **one,
        "event_id": str(uuid.uuid4()),
        "entity_id": str(uuid.uuid4()),
        "device_id": str(device.id),
        "payload": {
            **one["payload"],
            "version_id": str(uuid.uuid4()),
            "line_id": str(uuid.uuid4()),
        },
    }
    dispatch(second, two, fixed_type="TRANSFER_CREATE")
    barrier = Barrier(2)

    def run(actor, command):
        try:
            barrier.wait(timeout=10)
            return dispatch(actor, send_command(command))[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, first, one), pool.submit(run, second, two)]
        assert sorted(f.result(timeout=15) for f in futures) == [200, 409]
    assert Notification.objects.count() == 1
