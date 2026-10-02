import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, RoleAssignment, User
from apps.catalog.models import Location, Presentation
from apps.sync.commands import dispatch
from apps.traceability.models import Lot, Transfer, TransferLine, TransferVersion
from tests.test_access import assign
from tests.test_milking_confirm import complete_command, confirm_command

pytestmark = pytest.mark.django_db


def transfer_fixture(user):
    for code in ("PRODUCCION", "TRANSPORTE", "RECEPCION", "ADMIN"):
        Role.objects.get_or_create(code=code)
    command = complete_command(user)
    dispatch(user, command, fixed_type="MILKING_CREATE")
    dispatch(user, confirm_command(command))
    lot = Lot.objects.get()
    destination = Location.objects.create(code="PV", name="Punto", kind="PUNTO_VENTA")
    driver = User.objects.create_user(username="driver", name="Driver")
    receiver = User.objects.create_user(username="receiver", name="Receiver")
    assign(driver, "TRANSPORTE", lot.production.center)
    assign(receiver, "RECEPCION", destination)
    presentation = Presentation.objects.create(
        product=lot.production.product, name="Bolsa 1 L", content_base="1.000"
    )
    transfer = Transfer.objects.create(code="T1", creator=user)
    version = TransferVersion.objects.create(
        transfer=transfer,
        number=1,
        origin=lot.production.center,
        destination=destination,
        emitter=user,
        driver=driver,
        receiver=receiver,
    )
    TransferLine.objects.create(
        version=version,
        lot=lot,
        presentation=presentation,
        units="5",
        content_base_snapshot="1",
        quantity="5",
    )
    transfer.current_version = version
    transfer.save()
    return transfer, lot, driver, receiver, command


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def test_read_scopes_and_lot_provenance_without_cow_details(user):
    transfer, lot, driver, receiver, command = transfer_fixture(user)
    path = f"/api/v1/transfers/{transfer.id}"
    assert client_for(user).get(path).status_code == 200
    assert client_for(driver).get(path).status_code == 404
    transfer.state = "PENDIENTE_RECOGIDA"
    transfer.save()
    for actor in (driver, receiver):
        client = client_for(actor)
        assert client.get(path).status_code == 200
        response = client.get(f"/api/v1/lots/{lot.id}")
        assert response.status_code == 200 and response.json()["quantity"] == "5.500"
        assert "details" not in response.json()
        assert client.get("/api/v1/products").json()["results"][0]["id"] == str(
            lot.production.product_id
        )
        assert len(client.get("/api/v1/locations").json()["results"]) == 2
        assert client.get("/api/v1/presentations").json()["count"] == 1
        assert client.get(f"/api/v1/milkings/{command['entity_id']}").status_code == 404
    stranger = User.objects.create_user(username="stranger")
    assign(stranger, "TRANSPORTE", lot.production.center)
    assert client_for(stranger).get(path).status_code == 404
    RoleAssignment.objects.filter(user=driver).delete()
    assert client_for(driver).get(path).status_code == 404


def test_admin_and_timeline(user):
    transfer, lot, driver, receiver, command = transfer_fixture(user)
    admin = User.objects.create_user(username="admin")
    assign(admin, "ADMIN")
    assert client_for(admin).get(f"/api/v1/transfers/{transfer.id}").json()["capabilities"] == []
    version = transfer.current_version
    version.state, version.published_at = "PUBLICADA", timezone.now()
    version.save()
    data = client_for(admin).get(f"/api/v1/transfers/{transfer.id}/timeline").json()
    assert len(data) == 1 and data[0]["type"] == "VERSION_PUBLISHED"
