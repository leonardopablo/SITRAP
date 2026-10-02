import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import IntegrityError, connections, transaction

from apps.accounts.models import User
from apps.milk.models import Milking
from apps.sync.commands import dispatch
from apps.sync.models import Device
from apps.traceability.models import Lot
from tests.test_access import assign
from tests.test_milking_draft import setup_milking

pytestmark = pytest.mark.django_db


def complete_command(user):
    command, cows = setup_milking(user)
    command["payload"]["details"][0]["liters"] = "2.500"
    command["payload"]["details"][1]["liters"] = "3.000"
    return command


def confirm_command(command):
    return {
        **command,
        "event_id": str(uuid.uuid4()),
        "type": "MILKING_CONFIRM",
        "expected_version": 1,
        "payload": {"version_id": command["payload"]["version_id"], "lot_id": str(uuid.uuid4())},
    }


def test_confirm_sum_unique_lot_and_published_immutable(api, user):
    command = complete_command(user)
    assert api.post("/api/v1/milkings", command, format="json").status_code == 200
    confirm = confirm_command(command)
    path = f"/api/v1/milkings/{command['entity_id']}/confirm"
    response = api.post(path, confirm, format="json")
    assert response.status_code == 200, response.data
    result = response.json()["result"]
    assert result["quantity"] == "5.500" and result["state"] == "CONFIRMADA"
    assert result["lot_id"] == confirm["payload"]["lot_id"]
    assert api.post(path, confirm, format="json").json() == response.json()
    assert Lot.objects.count() == 1
    another = {**confirm, "event_id": str(uuid.uuid4()), "expected_version": 2}
    assert api.post(path, another, format="json").status_code == 409
    version = Milking.objects.get().production.current_version
    with pytest.raises(IntegrityError), transaction.atomic():
        version.details.update(liters="8.000")
    with pytest.raises(IntegrityError), transaction.atomic():
        version.quantity = "99.000"
        version.save()


@pytest.mark.parametrize("liters", [None, "0.000"])
def test_incomplete_zero_and_obsolete_document_cannot_confirm(api, user, liters):
    command, cows = setup_milking(user)
    command["payload"]["details"][0]["liters"] = liters
    assert api.post("/api/v1/milkings", command, format="json").status_code == 200
    path = f"/api/v1/milkings/{command['entity_id']}/confirm"
    confirm = confirm_command(command)
    assert api.post(path, confirm, format="json").status_code == 422
    assert not Lot.objects.exists()
    obsolete = confirm_command(command)
    obsolete["payload"]["version_id"] = str(uuid.uuid4())
    assert api.post(path, obsolete, format="json").status_code == 409
    # The client cannot supply a free total.
    assert (
        api.post(
            path, {**confirm, "payload": {**confirm["payload"], "liters": "50"}}, format="json"
        ).status_code
        == 422
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_two_producers_confirm_once():
    first = User.objects.create_user(username="first")
    command = complete_command(first)
    dispatch(first, command, fixed_type="MILKING_CREATE")
    second = User.objects.create_user(username="second")
    assign(second, "PRODUCCION", Milking.objects.get().center)
    device = Device.objects.create(user=second, name="second")
    one, two = confirm_command(command), confirm_command(command)
    two["device_id"] = str(device.id)
    barrier = Barrier(2)

    def run(actor, command):
        try:
            barrier.wait(timeout=10)
            return dispatch(actor, command)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, first, one), pool.submit(run, second, two)]
        assert sorted(future.result(timeout=15) for future in futures) == [200, 409]
    assert Lot.objects.count() == 1
    assert Milking.objects.get().production.state == "CONFIRMADA"
