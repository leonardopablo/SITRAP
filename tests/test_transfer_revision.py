import uuid

import pytest

from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.traceability.allocation import reserved_quantities
from apps.traceability.models import Conformity, Transfer
from tests.test_transfer_draft import draft_command
from tests.test_transfer_send import send_command

pytestmark = pytest.mark.django_db


def published(user):
    command = draft_command(user)
    dispatch(user, command, fixed_type="TRANSFER_CREATE")
    dispatch(user, send_command(command))
    return command, Transfer.objects.get(pk=command["entity_id"])


def revise_command(command, expected=2, units="4"):
    return {
        **command,
        "event_id": str(uuid.uuid4()),
        "type": "TRANSFER_REVISE",
        "expected_version": expected,
        "payload": {
            key: value
            for key, value in {
                **command["payload"],
                "version_id": str(uuid.uuid4()),
                "line_id": str(uuid.uuid4()),
                "units": units,
                "reason": "Ajuste antes de recogida",
            }.items()
            if key not in ("lot_id", "presentation_id")
        },
    }


def test_revision_preserves_history_replay_and_reserves_current_only(user):
    command, transfer = published(user)
    old_id = transfer.current_version_id
    revised = revise_command(command)
    result, status = dispatch(user, revised)
    assert status == 200, result
    assert dispatch(user, revised)[0] == result
    transfer.refresh_from_db()
    assert transfer.state == "PENDIENTE_RECOGIDA" and transfer.lock_version == 3
    assert transfer.versions.get(pk=old_id).state == "SUPERADA"
    assert (
        Conformity.objects.filter(version__transfer=transfer, stage="ENTREGA_ORIGEN").count() == 2
    )
    assert list(reserved_quantities().values()) == [4]
    assert Notification.objects.filter(type="PICKUP_REQUEST_UPDATED").count() == 1
    stale = {**revised, "event_id": str(uuid.uuid4())}
    assert dispatch(user, stale)[1] == 409


def test_cancel_releases_reservation_but_keeps_published_document(user):
    command, transfer = published(user)
    cancel = {
        **command,
        "type": "TRANSFER_CANCEL",
        "event_id": str(uuid.uuid4()),
        "expected_version": 2,
        "payload": {"reason": "No sale"},
    }
    assert dispatch(user, cancel)[1] == 200
    assert not reserved_quantities()
    transfer.refresh_from_db()
    assert transfer.state == "CANCELADO" and transfer.current_version.state == "PUBLICADA"
    assert Notification.objects.filter(type="TRANSFER_CANCELLED").count() == 1
    assert (
        dispatch(user, {**cancel, "event_id": str(uuid.uuid4()), "expected_version": 3})[1] == 409
    )


def test_revision_rejects_excess_and_logistics_change(user):
    command, transfer = published(user)
    result, status = dispatch(user, revise_command(command, units="6"))
    assert status == 409 and result["error"]["code"] == "ALLOCATION_EXCEEDED"
    assert transfer.versions.count() == 1
    transfer.state = "EN_CAMINO"
    transfer.save()
    assert dispatch(user, revise_command(command))[1] == 409
