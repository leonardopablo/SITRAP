import uuid
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import Presentation, Product
from apps.catalog.quantities import presentation_quantity
from apps.common.errors import DomainError
from tests.test_catalog import create_catalog

pytestmark = pytest.mark.django_db


def test_presentation_positive_indivisible_and_pilot_compatibility(api, user):
    _, product, _ = create_catalog(api, user)
    payload = {
        "id": str(uuid.uuid4()),
        "product_id": product["id"],
        "name": "Bolsa 1 L",
        "content_base": "1.000",
        "allows_fraction": False,
    }
    assert api.post("/api/v1/presentations", payload, format="json").status_code == 200
    presentation = Presentation.objects.get()
    assert presentation_quantity(presentation, "20", milk_pilot=True) == Decimal("20.000")
    for value in ("1.5", "0", "-1", "NaN", "Infinity", "0.0001"):
        with pytest.raises(DomainError):
            presentation_quantity(presentation, value, milk_pilot=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        Presentation.objects.filter(pk=presentation.pk).update(content_base=0)
    other = Product.objects.create(code="WEIGHT", name="Weight", unit_id="KG")
    presentation.product = other
    with pytest.raises(DomainError):
        presentation_quantity(presentation, "2", milk_pilot=True)


def test_catalogs_and_no_hidden_unit_conversion(api, user):
    _, product, _ = create_catalog(api, user)
    assert (
        api.post("/api/v1/units", {"code": "L", "name": "Litro"}, format="json").status_code == 200
    )
    assert api.patch("/api/v1/units/L", {"name": "Litros"}, format="json").status_code == 200
    assert (
        api.post("/api/v1/units", {"code": "GAL", "name": "Galón"}, format="json").status_code
        == 422
    )
    for route in ("species", "turns"):
        item = {"id": str(uuid.uuid4()), "code": "DEMO", "name": "Demo"}
        assert api.post(f"/api/v1/{route}", item, format="json").status_code == 200
        assert (
            api.patch(f"/api/v1/{route}/{item['id']}", {"active": False}, format="json").status_code
            == 200
        )
    bad = {
        "id": str(uuid.uuid4()),
        "product_id": product["id"],
        "name": "X",
        "content_base": "0",
        "allows_fraction": False,
    }
    assert api.post("/api/v1/presentations", bad, format="json").status_code == 422
    bad.update(content_base="1.000", unit_id="KG")
    assert api.post("/api/v1/presentations", bad, format="json").status_code == 422
