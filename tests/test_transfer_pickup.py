import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import connections

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.sync.models import Device
from apps.traceability.models import Conformity
from tests.test_access import assign
from tests.test_transfer_reads import client_for
from tests.test_transfer_revision import published, revise_command

pytestmark = pytest.mark.django_db


def physical_command(transfer, actor, type="TRANSFER_PICKUP"):
    device, _ = Device.objects.get_or_create(user=actor, name="physical")
    return {
        "event_id": str(uuid.uuid4()),
        "device_id": str(device.id),
        "type": type,
        "entity_id": str(transfer.id),
        "expected_version": transfer.lock_version,
        "occurred_at": "2026-10-02T09:00:00-05:00",
        "depends_on": [],
        "payload": {"version_id": str(transfer.current_version_id)},
    }


def test_pickup_copies_exact_version_once_and_notifies_receiver(user):
    command, transfer = published(user)
    driver = transfer.current_version.driver
    pickup = physical_command(transfer, driver)
    path = f"/api/v1/transfers/{transfer.id}/pickup"
    client = client_for(driver)
    response = client.post(path, pickup, format="json")
    assert response.status_code == 200, response.data
    assert client.post(path, pickup, format="json").json() == response.json()
    transfer.refresh_from_db()
    assert transfer.state == "EN_CAMINO"
    conformity = Conformity.objects.get(stage="RECOGIDA")
    assert conformity.user == driver and str(conformity.details.get().accepted_quantity) == "5.000"
    assert (
        Notification.objects.filter(
            type="RECEPTION_PENDING", recipient=transfer.current_version.receiver
        ).count()
        == 1
    )
    # A new event/document cannot repeat the physical stage.
    again = physical_command(transfer, driver)
    assert client.post(path, again, format="json").status_code == 409
    assert (
        client.post(
            path, {**again, "payload": {**again["payload"], "liters": "9"}}, format="json"
        ).status_code
        == 422
    )


def test_pickup_obsolete_document_and_admin_denied(user):
    command, transfer = published(user)
    driver = transfer.current_version.driver
    old = physical_command(transfer, driver)
    dispatch(user, revise_command(command))
    transfer.refresh_from_db()
    old["expected_version"] = transfer.lock_version
    assert (
        client_for(driver)
        .post(f"/api/v1/transfers/{transfer.id}/pickup", old, format="json")
        .status_code
        == 409
    )
    admin = User.objects.create_user(username="admin")
    assign(admin, "ADMIN")
    assert (
        client_for(admin)
        .post(
            f"/api/v1/transfers/{transfer.id}/pickup",
            physical_command(transfer, admin),
            format="json",
        )
        .status_code
        == 403
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_pickup_races_revision_without_two_effects():
    producer = User.objects.create_user(username="producer")
    command, transfer = published(producer)
    driver = transfer.current_version.driver
    pickup = physical_command(transfer, driver)
    revision = revise_command(command)
    barrier = Barrier(2)

    def run(actor, event):
        try:
            barrier.wait(timeout=10)
            return dispatch(actor, event)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, driver, pickup), pool.submit(run, producer, revision)]
        assert sorted(f.result(timeout=15) for f in futures) == [200, 409]
    transfer.refresh_from_db()
    assert transfer.lock_version == 3
    assert Conformity.objects.filter(stage="RECOGIDA").count() <= 1
