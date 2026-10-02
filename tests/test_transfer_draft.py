import uuid

import pytest
from django.utils import timezone

from apps.sync.models import Device
from apps.traceability.models import Transfer, TransferLine
from tests.test_transfer_reads import transfer_fixture

pytestmark = pytest.mark.django_db


def draft_command(user):
    reference, lot, driver, receiver, _ = transfer_fixture(user)
    return {
        "event_id": str(uuid.uuid4()),
        "device_id": str(Device.objects.filter(user=user).first().id),
        "entity_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "depends_on": [],
        "payload": {
            "version_id": str(uuid.uuid4()),
            "line_id": str(uuid.uuid4()),
            "lot_id": str(lot.id),
            "presentation_id": str(reference.current_version.lines.get().presentation_id),
            "units": "5.000",
            "destination_id": str(reference.current_version.destination_id),
            "driver_id": str(driver.id),
            "receiver_id": str(receiver.id),
        },
    }


def test_nested_draft_atomic_idempotent_and_edit_version(api, user):
    command = draft_command(user)
    first = api.post("/api/v1/transfers", command, format="json")
    assert first.status_code == 200, first.data
    assert first.json()["result"]["current_version"]["lines"][0]["quantity"] == "5.000"
    assert api.post("/api/v1/transfers", command, format="json").json() == first.json()
    transfer = Transfer.objects.get(pk=command["entity_id"])
    assert transfer.versions.count() == 1 and transfer.current_version.lines.count() == 1
    update = {
        **command,
        "event_id": str(uuid.uuid4()),
        "expected_version": 1,
        "payload": {**command["payload"], "units": "4"},
    }
    response = api.patch(f"/api/v1/transfers/{transfer.id}", update, format="json")
    assert response.status_code == 200 and response.json()["lock_version"] == 2
    stale = {**update, "event_id": str(uuid.uuid4())}
    assert api.patch(f"/api/v1/transfers/{transfer.id}", stale, format="json").status_code == 409


def test_invalid_participant_or_fraction_does_not_create_partial_draft(api, user):
    command = draft_command(user)
    count = Transfer.objects.count()
    bad = {**command, "payload": {**command["payload"], "units": "1.5"}}
    assert api.post("/api/v1/transfers", bad, format="json").status_code == 422
    assert Transfer.objects.count() == count
    bad = {
        **command,
        "event_id": str(uuid.uuid4()),
        "payload": {**command["payload"], "driver_id": str(uuid.uuid4())},
    }
    assert api.post("/api/v1/transfers", bad, format="json").status_code == 422
    assert Transfer.objects.count() == count
    assert not TransferLine.objects.filter(id=command["payload"]["line_id"]).exists()
