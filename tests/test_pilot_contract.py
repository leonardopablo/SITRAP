from datetime import date
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from drf_spectacular.generators import SchemaGenerator

from apps.accounts.models import RoleAssignment, User
from apps.milk.models import Milking
from tests.test_transfer_reads import client_for


def test_openapi_matches_implemented_schema():
    path = Path(__file__).resolve().parents[1] / "docs" / "openapi.yaml"
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == SchemaGenerator().get_schema(
        request=None, public=True
    )


@pytest.mark.django_db(transaction=True)
def test_demo_milk_is_confirmed_and_visible_to_metrics(settings):
    settings.DEBUG = True
    with pytest.raises(CommandError, match="--confirm-demo"):
        call_command("seed_milk_demo", date=date(2026, 10, 1))
    assert not Milking.objects.exists()
    call_command("seed_milk_demo", confirm_demo=True, date=date(2026, 10, 1))
    milking = Milking.objects.get()
    assert milking.production.state == "CONFIRMADA"
    assert milking.production.current_version.quantity == 5.5
    assert RoleAssignment.objects.get(user__username="demo_leche").location == milking.center
    actor = User.objects.get(username="demo_leche")
    assert not actor.has_usable_password()
    response = client_for(actor).get(
        "/api/v1/metrics/milk", {"date_from": "2026-10-01", "date_to": "2026-10-01"}
    )
    assert response.status_code == 200
    assert response.json()["liters"] == "5.500"
    with pytest.raises(CommandError, match="already exists"):
        call_command("seed_milk_demo", confirm_demo=True, date=date(2026, 10, 1))
    assert Milking.objects.count() == 1
    settings.DEBUG = False
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_milk_demo", confirm_demo=True, date=date(2026, 10, 2))
