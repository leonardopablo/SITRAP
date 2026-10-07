import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Barrier
from zoneinfo import ZoneInfo

import pytest
from django.db import connections
from django.utils import timezone

from apps.accounts.models import Role, RoleAssignment, User
from apps.catalog.models import (
    Animal,
    AnimalStay,
    CenterProduct,
    Location,
    Product,
    Species,
    Turn,
    Unit,
)
from apps.milk.models import Milking
from apps.sync.commands import dispatch
from apps.sync.models import Device
from tests.test_access import assign

pytestmark = pytest.mark.django_db


def setup_milking(user):
    # get_or_create also supports isolated transaction tests after a database flush.
    Role.objects.get_or_create(code="PRODUCCION")
    Unit.objects.get_or_create(code="L", defaults={"name": "Litro"})
    center = Location.objects.create(code="C1", name="Centro", kind="CENTRO")
    product = Product.objects.create(code="LECHE", name="Leche", unit_id="L")
    CenterProduct.objects.create(center=center, product=product)
    turn = Turn.objects.create(code="DIA", name="Diario")
    species = Species.objects.create(code="BOVINO", name="Bovino")
    cows = [Animal.objects.create(code=f"V{i}", species=species, sex="HEMBRA") for i in range(2)]
    for cow in cows:
        AnimalStay.objects.create(animal=cow, center=center, starts_on=date(2026, 1, 1))
    assign(user, "PRODUCCION", center)
    device = Device.objects.create(user=user, name="test")
    command = {
        "event_id": str(uuid.uuid4()),
        "device_id": str(device.id),
        "entity_id": str(uuid.uuid4()),
        "occurred_at": datetime(2026, 10, 1, 12, tzinfo=ZoneInfo("America/Lima")).isoformat(),
        "depends_on": [],
        "payload": {
            "production_id": str(uuid.uuid4()),
            "version_id": str(uuid.uuid4()),
            "center_id": str(center.id),
            "product_id": str(product.id),
            "date": "2026-10-01",
            "turn_id": str(turn.id),
            "details": [
                {"animal_id": str(cows[0].id), "liters": None},
                {"animal_id": str(cows[1].id), "liters": "0.000"},
            ],
        },
    }
    return command, cows


def update_command(command, liters="2.000"):
    return {
        **command,
        "type": "MILKING_UPDATE",
        "event_id": str(uuid.uuid4()),
        "expected_version": 1,
        "payload": {
            "date": command["payload"]["date"],
            "turn_id": command["payload"]["turn_id"],
            "details": [{**row, "liters": liters} for row in command["payload"]["details"]],
        },
    }


def test_draft_null_is_not_zero_and_idempotence(api, user):
    command, cows = setup_milking(user)
    response = api.post("/api/v1/milkings", command, format="json")
    assert response.status_code == 200, response.data
    result = response.json()["result"]
    assert sorted(str(row["liters"]) for row in result["details"]) == ["0.000", "None"]
    assert not result["complete"] and result["quantity"] == "0.000"
    assert api.post("/api/v1/milkings", command, format="json").json() == response.json()
    assert Milking.objects.count() == 1
    assert api.get(f"/api/v1/milkings/{command['entity_id']}").status_code == 200


def test_date_must_match_registration_day_in_peru_even_when_synced_later(user):
    command, _ = setup_milking(user)
    wrong = {**command, "payload": {**command["payload"], "date": "2026-10-02"}}
    response, status = dispatch(user, wrong, fixed_type="MILKING_CREATE")
    assert status == 422 and response["error"]["code"] == "VALIDATION_ERROR"
    assert not Milking.objects.exists()

    command["event_id"] = str(uuid.uuid4())
    response, status = dispatch(user, command, fixed_type="MILKING_CREATE")
    assert status == 200  # The event occurred on Oct 1; syncing on a later day is valid.
    update = update_command(command)
    update["payload"]["date"] = "2026-10-02"
    response, status = dispatch(user, update)
    assert status == 422 and Milking.objects.get().date.isoformat() == "2026-10-01"

    from tests.test_milking_confirm import confirm_command

    confirm = confirm_command(command)
    confirm["occurred_at"] = datetime(2026, 10, 2, 12, tzinfo=ZoneInfo("America/Lima")).isoformat()
    response, status = dispatch(user, confirm)
    assert status == 422 and Milking.objects.get().production.state == "BORRADOR"


def test_future_device_clock_cannot_register_tomorrows_milking(user):
    command, _ = setup_milking(user)
    future = timezone.now() + timedelta(days=1)
    command["occurred_at"] = future.isoformat()
    command["payload"]["date"] = future.astimezone(ZoneInfo("America/Lima")).date().isoformat()
    response, status = dispatch(user, command, fixed_type="MILKING_CREATE")
    assert status == 422 and response["error"]["code"] == "VALIDATION_ERROR"
    assert not Milking.objects.exists()


def test_utc_midnight_still_uses_peru_calendar_date(user):
    command, _ = setup_milking(user)
    command["occurred_at"] = "2026-10-02T00:30:00+00:00"  # Oct 1 at 19:30 in Peru.
    response, status = dispatch(user, command, fixed_type="MILKING_CREATE")
    assert status == 200 and response["result"]["date"] == "2026-10-01"


def test_update_checks_version_and_animal_scope(api, user):
    command, cows = setup_milking(user)
    assert api.post("/api/v1/milkings", command, format="json").status_code == 200
    update = update_command(command)
    response = api.patch(f"/api/v1/milkings/{command['entity_id']}", update, format="json")
    assert response.status_code == 200 and response.json()["lock_version"] == 2
    stale = {**update, "event_id": str(uuid.uuid4())}
    response = api.patch(f"/api/v1/milkings/{command['entity_id']}", stale, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "VERSION_CONFLICT"
    wrong = {
        **update,
        "event_id": str(uuid.uuid4()),
        "expected_version": 2,
        "payload": {
            **update["payload"],
            "details": [{"animal_id": str(uuid.uuid4()), "liters": "1.000"}],
        },
    }
    assert (
        api.patch(f"/api/v1/milkings/{command['entity_id']}", wrong, format="json").status_code
        == 422
    )
    RoleAssignment.objects.filter(user=user).delete()
    assert api.get(f"/api/v1/milkings/{command['entity_id']}").status_code == 404


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_concurrent_draft_edits_one_version_wins():
    user = User.objects.create_user(username="producer")
    command, cows = setup_milking(user)
    dispatch(user, command, fixed_type="MILKING_CREATE")
    barrier = Barrier(2)

    def edit(value):
        try:
            barrier.wait(timeout=10)
            return dispatch(user, update_command(command, value))[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(edit, value) for value in ("2.000", "3.000")]
        assert sorted(future.result(timeout=15) for future in futures) == [200, 409]
    assert Milking.objects.get().production.lock_version == 2
