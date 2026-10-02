import uuid

import pytest

from apps.accounts.models import RoleAssignment, User
from apps.sync.commands import dispatch
from tests.test_access import assign
from tests.test_correction_accept import decision_command
from tests.test_correction_create import pending_correction
from tests.test_transfer_pickup import physical_command
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db(transaction=True)
PERIOD = {"date_from": "2026-10-01", "date_to": "2026-10-03"}


def corrected_transfer(user):
    _, transfer, correction, _ = pending_correction(user)
    for actor in [correction.transport_approver, correction.reception_approver]:
        assert dispatch(actor, decision_command(correction, actor))[1] == 200
        correction.refresh_from_db()
    transfer.refresh_from_db()
    receiver = transfer.current_version.receiver
    event = physical_command(transfer, receiver, "TRANSFER_RECEIVE")
    event["occurred_at"] = "2026-10-03T04:30:00Z"
    assert dispatch(receiver, event)[1] == 200
    return transfer


def test_calendar_physical_lima_dates_and_corrected_current_quantity(user):
    transfer = corrected_transfer(user)
    data = client_for(user).get("/api/v1/metrics/transfers", PERIOD).json()
    assert data["picked_up_liters"] == data["received_liters"] == "4.000"
    assert data["picked_up_count"] == data["received_count"] == 1
    assert len(data["records"]) == 1 and data["records"][0]["corrected"]
    assert data["days"][1]["received_liters"] == "4.000"
    assert data["days"][2]["received_liters"] == "0.000"
    assert data["records"][0]["version_id"] == str(transfer.current_version_id)


def test_metrics_only_assigned_people_and_filters(user):
    transfer = corrected_transfer(user)
    driver = transfer.current_version.driver
    receiver = transfer.current_version.receiver
    for actor in [driver, receiver]:
        assert (
            client_for(actor).get("/api/v1/metrics/transfers", PERIOD).json()["received_liters"]
            == "4.000"
        )
    stranger = User.objects.create_user(username="stranger")
    assign(stranger, "TRANSPORTE", transfer.current_version.origin)
    assert client_for(stranger).get("/api/v1/metrics/transfers", PERIOD).json()["records"] == []
    RoleAssignment.objects.filter(user=driver).delete()
    assert client_for(driver).get("/api/v1/metrics/transfers", PERIOD).status_code == 403
    assert (
        client_for(user)
        .get("/api/v1/metrics/transfers", {**PERIOD, "destination_id": uuid.uuid4()})
        .json()["records"]
        == []
    )
