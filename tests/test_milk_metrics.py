import uuid

import pytest

from apps.accounts.models import Role, User
from apps.catalog.models import Animal, AnimalStay
from apps.milk.models import Milking
from apps.sync.commands import dispatch
from tests.test_access import assign
from tests.test_milking_confirm import complete_command, confirm_command
from tests.test_milking_rectification import rectify_command
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db(transaction=True)
PERIOD = {"date_from": "2026-10-01", "date_to": "2026-10-03"}


def confirmed(user):
    command = complete_command(user)
    command["payload"]["details"][0]["liters"] = "0.000"
    assert dispatch(user, command, fixed_type="MILKING_CREATE")[1] == 200
    assert dispatch(user, confirm_command(command))[1] == 200
    return Milking.objects.get()


def test_zero_absence_coverage_and_current_revision(user):
    milking = confirmed(user)
    cow = Animal.objects.create(code="ABSENT", species=Animal.objects.first().species, sex="HEMBRA")
    AnimalStay.objects.create(animal=cow, center=milking.center, starts_on="2026-10-01")
    client = client_for(user)
    data = client.get("/api/v1/metrics/milk", PERIOD).json()
    assert data["liters"] == "3.000" and data["recorded_days"] == 1
    assert data["days"][1]["liters"] is None
    zero = next(row for row in data["animals"] if row["code"] == "V0")
    absent = next(row for row in data["animals"] if row["code"] == "ABSENT")
    assert zero["average_per_recorded_day"] == "0.000" and zero["recorded_days"] == 1
    assert absent["average_per_recorded_day"] is None and absent["days_without_record"] == 3
    assert dispatch(user, rectify_command(milking, user, "4"))[1] == 200
    data = client.get("/api/v1/metrics/milk", PERIOD).json()
    assert data["liters"] == "8.000" and len(data["records"]) == 2
    milking.refresh_from_db()
    event = rectify_command(milking, user)
    event["type"], event["payload"] = "MILKING_VOID", {"reason": "Anular"}
    assert dispatch(user, event)[1] == 200
    data = client.get("/api/v1/metrics/milk", PERIOD).json()
    assert data["recorded_days"] == 0 and data["days"][0]["liters"] is None


def test_metrics_scope_filters_and_period_limits(user):
    milking = confirmed(user)
    outsider = User.objects.create_user(username="other")
    assert client_for(outsider).get("/api/v1/metrics/milk", PERIOD).status_code == 403
    client = client_for(user)
    assert (
        client.get("/api/v1/metrics/milk", {**PERIOD, "center_id": uuid.uuid4()}).status_code == 403
    )
    assert (
        client.get(
            "/api/v1/metrics/milk", {"date_from": "2025-01-01", "date_to": "2026-10-01"}
        ).status_code
        == 422
    )
    assert (
        client.get("/api/v1/metrics/milk", {**PERIOD, "turn_id": uuid.uuid4()}).json()["liters"]
        == "0.000"
    )
    Role.objects.get_or_create(code="ADMIN")
    assign(outsider, "ADMIN")
    assert client_for(outsider).get("/api/v1/metrics/milk", PERIOD).json()["liters"] == "3.000"
    assert (
        client.get("/api/v1/metrics/milk", {**PERIOD, "center_id": milking.center_id}).status_code
        == 200
    )
