import uuid

import pytest

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.traceability.models import Conformity
from tests.test_access import assign
from tests.test_correction_closing import withdraw_command
from tests.test_correction_create import pending_correction
from tests.test_transfer_pickup import physical_command
from tests.test_transfer_reads import client_for
from tests.test_transfer_receive import in_transit

pytestmark = pytest.mark.django_db


def setup_admin_reassignment(transfer):
    admin = User.objects.create_user(username="admin")
    assign(admin, "ADMIN")
    receiver = User.objects.create_user(username="replacement")
    assign(receiver, "RECEPCION", transfer.current_version.destination)
    data = {
        "id": str(uuid.uuid4()),
        "version_id": str(uuid.uuid4()),
        "line_id": str(uuid.uuid4()),
        "expected_version": transfer.lock_version,
        "receiver_id": str(receiver.id),
        "reason": "Reemplazo de turno",
    }
    return admin, receiver, data


def test_reassignment_preserves_pickup_and_only_new_receiver_can_receive(user):
    _, transfer = in_transit(user)
    old_receiver = transfer.current_version.receiver
    history = list(Conformity.objects.order_by("id").values())
    admin, receiver, data = setup_admin_reassignment(transfer)
    path = f"/api/v1/transfers/{transfer.id}/reassign-receiver"
    assert client_for(user).post(path, data, format="json").status_code == 403
    result = client_for(admin).post(path, data, format="json")
    assert result.status_code == 200, result.data
    assert client_for(admin).post(path, data, format="json").json() == result.json()
    assert list(Conformity.objects.order_by("id").values()) == history
    assert Notification.objects.filter(type="RECEIVER_REASSIGNED").count() == 4
    transfer.refresh_from_db()
    old_event = physical_command(transfer, old_receiver, "TRANSFER_RECEIVE")
    assert (
        client_for(old_receiver)
        .post(f"/api/v1/transfers/{transfer.id}/receive", old_event, format="json")
        .status_code
        == 403
    )
    assert dispatch(receiver, physical_command(transfer, receiver, "TRANSFER_RECEIVE"))[1] == 200
    data["id"], data["expected_version"] = str(uuid.uuid4()), transfer.lock_version + 1
    assert client_for(admin).post(path, data, format="json").status_code == 409


def test_any_historical_correction_prevents_reassignment(user):
    _, transfer, correction, _ = pending_correction(user)
    dispatch(user, withdraw_command(correction, user))
    transfer.refresh_from_db()
    admin, _, data = setup_admin_reassignment(transfer)
    result = client_for(admin).post(
        f"/api/v1/transfers/{transfer.id}/reassign-receiver", data, format="json"
    )
    assert result.status_code == 409
    assert not Notification.objects.filter(type="RECEIVER_REASSIGNED").exists()
