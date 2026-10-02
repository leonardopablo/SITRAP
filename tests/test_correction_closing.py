from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connections

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.traceability.allocation import reserved_quantities
from tests.test_correction_accept import decision_command
from tests.test_correction_create import pending_correction
from tests.test_transfer_pickup import physical_command

pytestmark = pytest.mark.django_db


def withdraw_command(correction, actor):
    event = decision_command(correction, actor, "CORRECTION_WITHDRAW", "Retiro por revisión")
    event["payload"].pop("version_id")
    return event


@pytest.mark.parametrize("action", ["REJECT", "WITHDRAW"])
def test_close_preserves_original_and_history_after_one_acceptance(user, action):
    _, transfer, correction, _ = pending_correction(user)
    assert (
        dispatch(
            correction.transport_approver,
            decision_command(correction, correction.transport_approver),
        )[1]
        == 200
    )
    correction.refresh_from_db()
    actor = correction.reception_approver if action == "REJECT" else user
    event = (
        decision_command(correction, actor, "CORRECTION_REJECT", "No corresponde")
        if action == "REJECT"
        else withdraw_command(correction, actor)
    )
    body, status = dispatch(actor, event)
    assert status == 200, body
    assert dispatch(actor, event)[0] == body
    correction.refresh_from_db()
    transfer.refresh_from_db()
    assert correction.state == ("RECHAZADA" if action == "REJECT" else "RETIRADA")
    assert (
        transfer.current_version_id == correction.original_version_id
        and transfer.state == "EN_CAMINO"
    )
    assert correction.proposed_version.state == "RETIRADA"
    assert correction.decisions.filter(decision="ACEPTAR").count() == 1
    assert list(reserved_quantities().values()) == [5]
    assert Notification.objects.filter(
        type="CORRECTION_REJECTED" if action == "REJECT" else "CORRECTION_WITHDRAWN"
    ).count() == (3 if action == "REJECT" else 2)
    receiver = correction.reception_approver
    assert dispatch(receiver, physical_command(transfer, receiver, "TRANSFER_RECEIVE"))[1] == 200


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_second_acceptance_races_withdrawal_with_one_terminal_result():
    producer = User.objects.create_user(username="producer")
    _, _, correction, _ = pending_correction(producer)
    dispatch(
        correction.transport_approver, decision_command(correction, correction.transport_approver)
    )
    correction.refresh_from_db()
    receiver = correction.reception_approver
    accept = decision_command(correction, receiver)
    withdraw = withdraw_command(correction, producer)
    barrier = Barrier(2)

    def run(actor, command):
        try:
            barrier.wait(timeout=10)
            return dispatch(actor, command)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, receiver, accept), pool.submit(run, producer, withdraw)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409]
    correction.refresh_from_db()
    assert correction.state in ["APLICADA", "RETIRADA"]
    assert Notification.objects.filter(
        type__in=["CORRECTION_APPLIED", "CORRECTION_WITHDRAWN"]
    ).count() in [2, 3]
