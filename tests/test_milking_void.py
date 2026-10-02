import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import IntegrityError, connections, transaction

from apps.accounts.models import User
from apps.common.errors import DomainError
from apps.milk.models import Milking
from apps.milk.voiding import void_internal
from apps.production.models import Production
from apps.sync.commands import dispatch
from apps.sync.models import Device
from apps.traceability.models import Lot
from tests.test_access import assign
from tests.test_milking_confirm import complete_command, confirm_command

pytestmark = pytest.mark.django_db


def replacement(command):
    return {
        **command,
        "event_id": str(uuid.uuid4()),
        "entity_id": str(uuid.uuid4()),
        "payload": {
            **command["payload"],
            "production_id": str(uuid.uuid4()),
            "version_id": str(uuid.uuid4()),
            "replaces_id": command["entity_id"],
        },
    }


def test_void_preserves_history_and_new_lot_for_replacement(user, api):
    command = complete_command(user)
    dispatch(user, command, fixed_type="MILKING_CREATE")
    confirmation = confirm_command(command)
    dispatch(user, confirmation)
    old = Milking.objects.get()
    result = void_internal(user, old.id, 2, "Fecha equivocada")
    assert result["state"] == "ANULADA"
    old.refresh_from_db()
    assert old.voided_at is not None
    assert old.production.current_version.state == "PUBLICADA"
    new = replacement(command)
    response, status = dispatch(user, new, fixed_type="MILKING_CREATE")
    assert status == 200 and response["result"]["replaces_id"] == str(old.id)
    dispatch(user, confirm_command(new))
    assert Lot.objects.count() == 2
    assert Milking.objects.count() == Production.objects.count() == 2
    assert api.post(f"/api/v1/milkings/{old.id}/void", {}, format="json").status_code == 422


def test_partial_unique_and_required_reason(user):
    command = complete_command(user)
    dispatch(user, command, fixed_type="MILKING_CREATE")
    original = Milking.objects.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        other = Production.objects.create(
            center=original.center, product=original.production.product, responsible=user
        )
        Milking.objects.create(
            production=other, center=original.center, date=original.date, turn=original.turn
        )
    with pytest.raises(DomainError):
        void_internal(user, original.id, 1, "")
    assert Milking.objects.get().voided_at is None
    assert Milking.objects.get().production.state == "BORRADOR"


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_void_and_recreate_race_keeps_one_active_key():
    actor = User.objects.create_user(username="producer")
    command = complete_command(actor)
    dispatch(actor, command, fixed_type="MILKING_CREATE")
    new = replacement(command)
    second_actor = User.objects.create_user(username="replacement_producer")
    assign(second_actor, "PRODUCCION", Milking.objects.get().center)
    new["device_id"] = str(Device.objects.create(user=second_actor, name="second").id)
    barrier = Barrier(2)

    def void():
        try:
            barrier.wait(timeout=10)
            return void_internal(actor, command["entity_id"], 1, "Replace")
        finally:
            connections.close_all()

    def recreate():
        try:
            barrier.wait(timeout=10)
            return dispatch(second_actor, new, fixed_type="MILKING_CREATE")
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(void), pool.submit(recreate)
        first.result(timeout=15)
        result, status = second.result(timeout=15)
    if status != 200:
        # A rejected intent stays rejected; deliberate retry after refresh uses a new UUID.
        new["event_id"] = str(uuid.uuid4())
        result, status = dispatch(second_actor, new, fixed_type="MILKING_CREATE")
    assert status == 200
    assert Milking.objects.filter(voided_at__isnull=True).count() == 1
    assert Milking.objects.filter(voided_at__isnull=False).count() == 1
