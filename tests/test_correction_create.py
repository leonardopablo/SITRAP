import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.traceability.allocation import reserved_quantities
from apps.traceability.correction_models import Correction
from tests.test_transfer_pickup import physical_command
from tests.test_transfer_reads import client_for
from tests.test_transfer_receive import in_transit

pytestmark = pytest.mark.django_db


def correction_command(command, transfer, units="4"):
    return {
        **command,
        "type": "CORRECTION_CREATE",
        "event_id": str(uuid.uuid4()),
        "expected_version": transfer.lock_version,
        "payload": {
            "correction_id": str(uuid.uuid4()),
            "version_id": str(uuid.uuid4()),
            "line_id": str(uuid.uuid4()),
            "units": units,
            "reason": "Cantidad documental revisada",
        },
    }


def pending_correction(user):
    command, transfer = in_transit(user)
    event = correction_command(command, transfer)
    body, status = dispatch(user, event)
    assert status == 200, body
    return command, transfer, Correction.objects.get(pk=event["payload"]["correction_id"]), event


def test_fixed_proposal_approvers_block_reception_and_keep_max_reservation(user):
    command, transfer, correction, event = pending_correction(user)
    assert dispatch(user, event)[1] == 200
    assert correction.transport_approver_id == transfer.current_version.driver_id
    assert correction.reception_approver_id == transfer.current_version.receiver_id
    assert list(reserved_quantities().values()) == [5]
    assert Notification.objects.filter(type="CORRECTION_REQUESTED").count() == 2
    transfer.refresh_from_db()
    receiver = transfer.current_version.receiver
    receive = physical_command(transfer, receiver, "TRANSFER_RECEIVE")
    body, status = dispatch(receiver, receive)
    assert status == 409 and body["error"]["code"] == "CORRECTION_PENDING"
    assert (
        "receive"
        not in client_for(receiver).get(f"/api/v1/transfers/{transfer.id}").json()["capabilities"]
    )
    view = client_for(receiver).get(f"/api/v1/corrections/{correction.id}")
    assert view.status_code == 200 and len(view.json()["pending_approvers"]) == 2
    assert (
        dispatch(user, correction_command(command, transfer))[0]["error"]["code"]
        == "CORRECTION_PENDING"
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        correction.proposed_version.lines.update(quantity="3")


def test_correction_cannot_exceed_production_and_no_partial_effect(user):
    command, transfer = in_transit(user)
    result, status = dispatch(user, correction_command(command, transfer, "6"))
    assert status == 409 and result["error"]["code"] == "ALLOCATION_EXCEEDED"
    assert not Correction.objects.exists()
    assert transfer.versions.count() == 1
    assert not Notification.objects.filter(type="CORRECTION_REQUESTED").exists()


def test_increase_reserves_proposed_maximum_and_approvers_cannot_change(user):
    from apps.accounts.models import User
    from tests.test_access import assign
    from tests.test_transfer_revision import published, revise_command

    command, transfer = published(user)
    assert dispatch(user, revise_command(command, units="3"))[1] == 200
    transfer.refresh_from_db()
    dispatch(
        transfer.current_version.driver, physical_command(transfer, transfer.current_version.driver)
    )
    transfer.refresh_from_db()
    assert dispatch(user, correction_command(command, transfer, "5"))[1] == 200
    assert list(reserved_quantities().values()) == [5]
    correction = Correction.objects.get()
    stranger = User.objects.create_user(username="unassigned-driver")
    assign(stranger, "TRANSPORTE", transfer.current_version.origin)
    assert client_for(stranger).get(f"/api/v1/corrections/{correction.id}").status_code == 404
    with pytest.raises(IntegrityError), transaction.atomic():
        Correction.objects.filter(pk=correction.id).update(transport_approver=stranger)
