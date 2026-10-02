import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connections

from apps.accounts.models import User
from apps.milk.models import Milking
from apps.sync.commands import dispatch
from apps.sync.models import Device
from apps.traceability.models import Transfer
from tests.test_access import assign
from tests.test_correction_accept import decision_command
from tests.test_correction_create import pending_correction
from tests.test_transfer_draft import draft_command
from tests.test_transfer_reads import client_for
from tests.test_transfer_send import send_command

pytestmark = pytest.mark.django_db


def rectify_command(milking, actor, liters="2"):
    device, _ = Device.objects.get_or_create(user=actor, name="rectify")
    return {
        "event_id": str(uuid.uuid4()),
        "device_id": str(device.id),
        "entity_id": str(milking.id),
        "type": "MILKING_RECTIFY",
        "occurred_at": "2026-10-02T12:30:00-05:00",
        "expected_version": milking.production.lock_version,
        "depends_on": [],
        "payload": {
            "version_id": str(uuid.uuid4()),
            "reason": "Corregir litros",
            "details": [
                {"animal_id": str(cow), "liters": liters}
                for cow in milking.production.current_version.details.values_list(
                    "animal_id", flat=True
                )
            ],
        },
    }


def test_rectify_covers_pending_max_and_preserves_versions_and_transfer(user):
    _, transfer, correction, _ = pending_correction(user)
    milking = Milking.objects.get()
    event = rectify_command(milking, user)
    assert dispatch(user, event)[0]["error"]["code"] == "ALLOCATION_EXCEEDED"
    for actor in [correction.transport_approver, correction.reception_approver]:
        assert dispatch(actor, decision_command(correction, actor))[1] == 200
        correction.refresh_from_db()
    event["event_id"] = str(uuid.uuid4())
    response = client_for(user).post(f"/api/v1/milkings/{milking.id}/rectify", event, format="json")
    assert response.status_code == 200, response.data
    assert response.json()["result"]["quantity"] == "4.000"
    assert len(response.json()["result"]["versions"]) == 2
    assert response.json()["result"]["versions"][0]["quantity"] == "5.500"
    assert dispatch(user, event)[0] == response.json()
    transfer.refresh_from_db()
    assert (
        transfer.state == "EN_CAMINO"
        and str(transfer.current_version.lines.get().quantity) == "4.000"
    )


def test_void_public_blocks_links_and_releases_unlinked_period(user):
    command = draft_command(user)
    dispatch(user, command, fixed_type="TRANSFER_CREATE")
    milking = Milking.objects.get()
    event = rectify_command(milking, user)
    event["type"], event["payload"] = "MILKING_VOID", {"reason": "Anular prueba"}
    path = f"/api/v1/milkings/{milking.id}/void"
    dispatch(user, send_command(command))
    assert client_for(user).post(path, event, format="json").status_code == 409
    cancel = {
        **command,
        "type": "TRANSFER_CANCEL",
        "event_id": str(uuid.uuid4()),
        "expected_version": 2,
        "payload": {"reason": "Cancelar"},
    }
    assert dispatch(user, cancel)[1] == 200
    event["event_id"] = str(uuid.uuid4())
    assert client_for(user).post(path, event, format="json").status_code == 200
    milking.refresh_from_db()
    assert milking.voided_at and milking.production.state == "ANULADA"


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_rectification_and_publication_share_production_lock():
    first = User.objects.create_user(username="first")
    command = draft_command(first)
    dispatch(first, command, fixed_type="TRANSFER_CREATE")
    second = User.objects.create_user(username="second")
    milking = Milking.objects.get()
    assign(second, "PRODUCCION", milking.center)
    reduction = rectify_command(milking, second)
    sending = send_command(command)
    barrier = Barrier(2)

    def run(actor, event):
        try:
            barrier.wait(timeout=10)
            return dispatch(actor, event)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, first, sending), pool.submit(run, second, reduction)]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409]
    milking.refresh_from_db()
    published = Transfer.objects.filter(state="PENDIENTE_RECOGIDA").exists()
    assert (published and milking.production.current_version.quantity == 5.5) or (
        not published and milking.production.current_version.quantity == 4
    )


def test_rectification_uses_historical_cows_and_rejects_date_changes(user):
    from apps.catalog.models import Animal

    draft_command(user)
    milking = Milking.objects.get()
    event = rectify_command(milking, user, "3")
    Animal.objects.update(status="INACTIVO")
    assert dispatch(user, event)[1] == 200
    milking.refresh_from_db()
    assert milking.production.current_version.quantity == 6
    event = rectify_command(milking, user)
    event["payload"]["date"] = "2026-10-01"
    assert (
        client_for(user)
        .post(f"/api/v1/milkings/{milking.id}/rectify", event, format="json")
        .status_code
        == 422
    )
