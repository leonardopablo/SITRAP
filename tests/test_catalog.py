import uuid

import pytest

from apps.accounts.models import RoleAssignment
from apps.audit.models import AuditEntry
from apps.catalog.models import CenterProduct, Location, Product
from tests.test_access import assign

pytestmark = pytest.mark.django_db


def create_catalog(api, user):
    assign(user, "ADMIN")
    center = {"id": str(uuid.uuid4()), "code": "C1", "name": "Centro", "kind": "CENTRO"}
    product = {"id": str(uuid.uuid4()), "code": "LECHE", "name": "Leche", "unit_id": "L"}
    assert api.post("/api/v1/locations", center, format="json").status_code == 200
    assert api.post("/api/v1/products", product, format="json").status_code == 200
    link = {"id": str(uuid.uuid4()), "center_id": center["id"], "product_id": product["id"]}
    assert api.post("/api/v1/center-products", link, format="json").status_code == 200
    return center, product, link


def test_admin_creation_idempotence_and_no_stock(api, user):
    center, product, link = create_catalog(api, user)
    assert api.post("/api/v1/locations", center, format="json").status_code == 200
    assert (
        api.post("/api/v1/products", {**product, "stock": "50"}, format="json").status_code == 422
    )
    assert Location.objects.count() == Product.objects.count() == CenterProduct.objects.count() == 1
    assert AuditEntry.objects.filter(action="SAVE_CATALOG").count() == 3
    assert api.delete(f"/api/v1/products/{product['id']}").status_code == 405


def test_scope_and_deactivation_preserve_history(api, user):
    center, product, link = create_catalog(api, user)
    other = Location.objects.create(code="OTHER", name="Other", kind="CENTRO")
    RoleAssignment.objects.filter(user=user).delete()
    assign(user, "PRODUCCION", other)
    assert api.get("/api/v1/products").json()["results"] == []
    assert (
        api.patch(f"/api/v1/products/{product['id']}", {"active": False}, format="json").status_code
        == 403
    )
    assign(user, "PRODUCCION", Location.objects.get(pk=center["id"]))
    assert api.get("/api/v1/products").json()["results"][0]["id"] == product["id"]
    assign(user, "ADMIN")
    assert (
        api.patch(f"/api/v1/products/{product['id']}", {"active": False}, format="json").status_code
        == 200
    )
    RoleAssignment.objects.filter(user=user, role_id="ADMIN").delete()
    assert api.get("/api/v1/products").json()["results"] == []
    assert Product.objects.filter(pk=product["id"], active=False).exists()
    assert CenterProduct.objects.filter(pk=link["id"]).exists()


def test_center_product_must_be_center_and_identity_cannot_change(api, user):
    center, product, link = create_catalog(api, user)
    point = Location.objects.create(code="PV", name="Point", kind="PUNTO_VENTA")
    response = api.post(
        "/api/v1/center-products",
        {
            "id": str(uuid.uuid4()),
            "center_id": str(point.id),
            "product_id": product["id"],
        },
        format="json",
    )
    assert response.status_code == 422
    assert (
        api.patch(f"/api/v1/products/{product['id']}", {"unit_id": "KG"}, format="json").status_code
        == 422
    )
    assert (
        api.patch(
            f"/api/v1/locations/{center['id']}", {"kind": "PUNTO_VENTA"}, format="json"
        ).status_code
        == 422
    )
