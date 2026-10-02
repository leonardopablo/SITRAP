import pytest

from apps.accounts.models import User
from apps.catalog.models import Location
from tests.test_access import assign

pytestmark = pytest.mark.django_db


def test_scope_minimal_fields_and_single_defaults(api, user):
    origin = Location.objects.create(code="C", name="Centro", kind="CENTRO")
    destination = Location.objects.create(code="PV", name="Punto", kind="PUNTO_VENTA")
    driver = User.objects.create_user(
        username="driver", name="Conductor", email="secret@example.test"
    )
    receiver = User.objects.create_user(username="receiver", name="Receptor")
    assign(user, "PRODUCCION", origin)
    assign(driver, "TRANSPORTE", origin)
    assign(receiver, "RECEPCION", destination)
    response = api.get("/api/v1/assignment-options", {"origin_id": str(origin.id)})
    assert response.status_code == 200
    data = response.json()
    assert data["drivers"] == [{"id": str(driver.id), "name": "Conductor"}]
    assert data["defaults"] == {
        "driver_id": str(driver.id),
        "destination_id": str(destination.id),
        "receiver_id": str(receiver.id),
    }
    assert api.get("/api/v1/users").status_code == 403
    other = Location.objects.create(code="OTHER", name="Otro", kind="CENTRO")
    assert api.get("/api/v1/assignment-options", {"origin_id": str(other.id)}).status_code == 403
    assert (
        api.get(
            "/api/v1/assignment-options",
            {"origin_id": str(origin.id), "destination_id": str(other.id)},
        ).status_code
        == 422
    )


def test_ambiguous_and_inactive_users_not_defaulted(api, user):
    origin = Location.objects.create(code="C", name="Centro", kind="CENTRO")
    assign(user, "PRODUCCION", origin)
    first = User.objects.create_user(username="one", name="One")
    second = User.objects.create_user(username="two", name="Two")
    assign(first, "TRANSPORTE", origin)
    assign(second, "TRANSPORTE", origin)
    params = {"origin_id": str(origin.id)}
    assert api.get("/api/v1/assignment-options", params).json()["defaults"]["driver_id"] is None
    second.is_active = False
    second.save()
    assert api.get("/api/v1/assignment-options", params).json()["defaults"]["driver_id"] == str(
        first.id
    )
