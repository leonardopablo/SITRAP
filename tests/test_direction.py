from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import RoleAssignment, User
from tests.test_cuyes import farm, item, send  # noqa: F401
from tests.test_milking_confirm import complete_command, confirm_command
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db
URL = "/api/v1/direction/dashboard"


def test_director_role_is_assignable_global_and_cannot_manage_accounts(farm):  # noqa: F811
    director = User.objects.create_user(username="direccion-test", name="Dirección")
    client = client_for(farm["admin"])
    payload = dict(id=str(uuid4()), user_id=str(director.id), role="DIRECTOR",
                   scope="GLOBAL", location_id=None, starts_at=(timezone.now() - timedelta(seconds=1)).isoformat())
    response = client.post("/api/v1/role-assignments", payload, format="json")
    assert response.status_code == 200, response.data
    assert client_for(director).get(URL).status_code == 200
    assert client_for(director).get("/api/v1/users").status_code == 403
    assert client_for(director).get("/api/v1/cuyes/sales/options").status_code == 403
    assert client_for(director).post(URL, {}, format="json").status_code == 405
    assert client_for(farm["worker"]).get(URL).status_code == 403
    assert APIClient().get(URL).status_code == 401
    RoleAssignment.objects.filter(pk=payload["id"]).update(ends_at=timezone.now())
    assert client_for(director).get(URL).status_code == 403


def test_direction_stock_refresh_and_scope(farm):  # noqa: F811
    admin = client_for(farm["admin"])
    endpoint = f"{URL}?center_id={farm['can'].id}"
    assert admin.get(endpoint).json()["results"][0]["cuyes"]["population"] == 0
    send(farm["worker"], "OPEN", pen_id=str(farm["p1"].id), lot={"provenance": "Prueba"},
         items=[item(category="MACHO", quality="A", quantity=10)])
    response = admin.get(endpoint)
    result, = response.json()["results"]
    assert result["cuyes"]["population"] == 10
    assert response["Cache-Control"] == "no-store, private"
    assert admin.get(f"{URL}?start=2026-02-01&end=2026-01-01").status_code == 422


def test_direction_milk_uses_confirmed_current_version(user, farm):  # noqa: F811
    producer = client_for(user)
    command = complete_command(user)
    assert producer.post("/api/v1/milkings", command, format="json").status_code == 200
    endpoint = f"/api/v1/milkings/{command['entity_id']}/confirm"
    assert producer.post(endpoint, confirm_command(command), format="json").status_code == 200
    payload = command["payload"]
    response = client_for(farm["admin"]).get(
        f"{URL}?center_id={payload['center_id']}&start={payload['date']}&end={payload['date']}"
    )
    assert response.status_code == 200
    row, = response.json()["results"]
    assert row["milk"]["liters"] == "5.500"
    assert row["activity"][0]["milkings"] == 1


def test_demo_reset_rejects_regular_database():
    with pytest.raises(CommandError, match="bloqueada"):
        call_command("seed_direction_demo")
