import uuid

import pytest

from apps.accounts.models import RoleAssignment, User
from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.sync.models import Device
from apps.traceability.models import Conformity
from tests.test_access import assign
from tests.test_correction_create import pending_correction
from tests.test_transfer_pickup import physical_command
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db


def decision_command(correction, actor, type="CORRECTION_ACCEPT", reason=None):
    device, _ = Device.objects.get_or_create(user=actor, name="decision")
    payload = {"version_id": str(correction.proposed_version_id)}
    if reason:
        payload["reason"] = reason
    return {
        "event_id": str(uuid.uuid4()),
        "device_id": str(device.id),
        "type": type,
        "entity_id": str(correction.id),
        "occurred_at": "2026-10-02T12:00:00-05:00",
        "expected_version": correction.lock_version,
        "depends_on": [],
        "payload": payload,
    }


@pytest.mark.parametrize("first_role", ["transport_approver", "reception_approver"])
def test_two_acceptances_apply_and_keep_physical_history(user, first_role):
    command, transfer, correction, _ = pending_correction(user)
    physical = list(Conformity.objects.filter(stage="RECOGIDA").values())
    first = getattr(correction, first_role)
    second = (
        correction.reception_approver
        if first_role == "transport_approver"
        else correction.transport_approver
    )
    event = decision_command(correction, first)
    response = client_for(first).post(
        f"/api/v1/corrections/{correction.id}/accept", event, format="json"
    )
    assert response.status_code == 200, response.data
    assert dispatch(first, event)[0] == response.json()
    correction.refresh_from_db()
    transfer.refresh_from_db()
    assert (
        correction.state == "PENDIENTE"
        and transfer.current_version_id == correction.original_version_id
    )
    stale = decision_command(correction, second)
    stale["expected_version"] = 1
    assert dispatch(second, stale)[1] == 409
    event = decision_command(correction, second)
    assert dispatch(second, event)[1] == 200
    correction.refresh_from_db()
    transfer.refresh_from_db()
    assert correction.state == "APLICADA" and transfer.state == "EN_CAMINO"
    assert transfer.current_version_id == correction.proposed_version_id
    assert list(Conformity.objects.filter(stage="RECOGIDA").values()) == physical
    assert not Conformity.objects.filter(stage="RECEPCION").exists()
    assert Notification.objects.filter(type="CORRECTION_APPLIED").count() == 3
    receiver = transfer.current_version.receiver
    assert dispatch(receiver, physical_command(transfer, receiver, "TRANSFER_RECEIVE"))[1] == 200
    assert str(Conformity.objects.get(stage="RECEPCION").details.get().accepted_quantity) == "4.000"


def test_admin_and_revoked_approver_cannot_apply(user):
    command, transfer, correction, _ = pending_correction(user)
    admin = User.objects.create_user(username="admin")
    assign(admin, "ADMIN")
    assert (
        client_for(admin)
        .post(
            f"/api/v1/corrections/{correction.id}/accept",
            decision_command(correction, admin),
            format="json",
        )
        .status_code
        == 403
    )
    driver = correction.transport_approver
    assert dispatch(driver, decision_command(correction, driver))[1] == 200
    correction.refresh_from_db()
    RoleAssignment.objects.filter(user=driver).delete()
    body, status = dispatch(
        correction.reception_approver, decision_command(correction, correction.reception_approver)
    )
    assert status == 403
    correction.refresh_from_db()
    assert correction.state == "PENDIENTE" and correction.decisions.count() == 1


def test_correction_of_received_transfer_never_recreates_physical_signatures(user):
    from unittest.mock import patch

    from apps.traceability.correction_models import Correction
    from tests.test_correction_create import correction_command
    from tests.test_transfer_receive import in_transit

    command, transfer = in_transit(user)
    receiver = transfer.current_version.receiver
    dispatch(receiver, physical_command(transfer, receiver, "TRANSFER_RECEIVE"))
    transfer.refresh_from_db()
    signatures = list(Conformity.objects.order_by("id").values())
    assert dispatch(user, correction_command(command, transfer))[1] == 200
    correction = Correction.objects.get()
    dispatch(
        correction.transport_approver, decision_command(correction, correction.transport_approver)
    )
    correction.refresh_from_db()
    event = decision_command(correction, receiver)
    with patch("apps.traceability.decisions.notify", side_effect=RuntimeError("outbox failed")):
        with pytest.raises(RuntimeError):
            dispatch(receiver, event)
    correction.refresh_from_db()
    assert correction.state == "PENDIENTE" and correction.decisions.count() == 1
    assert dispatch(receiver, event)[1] == 200
    transfer.refresh_from_db()
    assert transfer.state == "RECIBIDO"
    assert list(Conformity.objects.order_by("id").values()) == signatures
    assert Notification.objects.filter(type="RECEPTION_PENDING").count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_concurrent_approvers_require_review_of_new_lock_version():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import connections

    producer = User.objects.create_user(username="producer")
    _, _, correction, _ = pending_correction(producer)
    actors = [correction.transport_approver, correction.reception_approver]
    commands = [decision_command(correction, actor) for actor in actors]
    barrier = Barrier(2)

    def run(actor, command):
        try:
            barrier.wait(timeout=10)
            return dispatch(actor, command)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, actor, command) for actor, command in zip(actors, commands)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409]
    correction.refresh_from_db()
    assert correction.state == "PENDIENTE" and correction.decisions.count() == 1
