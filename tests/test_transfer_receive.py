import uuid

import pytest

from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.traceability.models import Conformity
from tests.test_transfer_pickup import physical_command
from tests.test_transfer_reads import client_for
from tests.test_transfer_revision import published

pytestmark = pytest.mark.django_db


def in_transit(user):
    command, transfer = published(user)
    dispatch(
        transfer.current_version.driver, physical_command(transfer, transfer.current_version.driver)
    )
    transfer.refresh_from_db()
    return command, transfer


def test_receive_physical_once_and_notify_emitter_driver(user):
    command, transfer = in_transit(user)
    receiver = transfer.current_version.receiver
    event = physical_command(transfer, receiver, "TRANSFER_RECEIVE")
    path = f"/api/v1/transfers/{transfer.id}/receive"
    response = client_for(receiver).post(path, event, format="json")
    assert response.status_code == 200, response.data
    assert client_for(receiver).post(path, event, format="json").json() == response.json()
    transfer.refresh_from_db()
    assert transfer.state == "RECIBIDO" and transfer.lock_version == 4
    assert Conformity.objects.filter(stage="RECOGIDA").count() == 1
    assert Conformity.objects.filter(stage="RECEPCION").count() == 1
    note_recipients = set(
        Notification.objects.filter(type="RECEPTION_CONFIRMED").values_list(
            "recipient_id", flat=True
        )
    )
    assert note_recipients == {user.id, transfer.current_version.driver_id}
    event["event_id"] = str(uuid.uuid4())
    event["expected_version"] = 4
    assert client_for(receiver).post(path, event, format="json").status_code == 409


def test_receive_requires_transit_assignment_and_exact_version(user):
    command, transfer = published(user)
    receiver = transfer.current_version.receiver
    event = physical_command(transfer, receiver, "TRANSFER_RECEIVE")
    path = f"/api/v1/transfers/{transfer.id}/receive"
    assert client_for(receiver).post(path, event, format="json").status_code == 409
    dispatch(
        transfer.current_version.driver, physical_command(transfer, transfer.current_version.driver)
    )
    transfer.refresh_from_db()
    event = physical_command(transfer, receiver, "TRANSFER_RECEIVE")
    event["payload"]["version_id"] = str(uuid.uuid4())
    assert client_for(receiver).post(path, event, format="json").status_code == 409
    assert (
        client_for(user)
        .post(path, physical_command(transfer, user, "TRANSFER_RECEIVE"), format="json")
        .status_code
        == 403
    )
    assert not Conformity.objects.filter(stage="RECEPCION").exists()
