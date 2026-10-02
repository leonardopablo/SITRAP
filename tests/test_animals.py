import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from django.db import IntegrityError, connections, transaction

from apps.catalog.models import Animal, AnimalStay, Location, Species
from tests.test_access import assign

pytestmark = pytest.mark.django_db


def animal_payload(center, species):
    return {
        "id": str(uuid.uuid4()),
        "code": "V001",
        "species_id": str(species.id),
        "sex": "HEMBRA",
        "name": "Vaca",
        "stay_id": str(uuid.uuid4()),
        "center_id": str(center.id),
        "starts_on": "2026-01-01",
    }


def test_animal_scope_initial_stay_and_admin_move(api, user):
    own = Location.objects.create(code="C1", name="Uno", kind="CENTRO")
    other = Location.objects.create(code="C2", name="Dos", kind="CENTRO")
    species = Species.objects.create(code="BOVINO", name="Bovino")
    assign(user, "PRODUCCION", own)
    payload = animal_payload(own, species)
    assert api.post("/api/v1/animals", payload, format="json").status_code == 200
    assert api.post("/api/v1/animals", payload, format="json").status_code == 200
    assert Animal.objects.count() == AnimalStay.objects.count() == 1
    animal_id = payload["id"]
    new_stay = {"id": str(uuid.uuid4()), "center_id": str(other.id), "starts_on": "2026-02-01"}
    assert (
        api.post(f"/api/v1/animals/{animal_id}/stays", new_stay, format="json").status_code == 403
    )
    assign(user, "ADMIN")
    assert (
        api.post(f"/api/v1/animals/{animal_id}/stays", new_stay, format="json").status_code == 200
    )
    assert AnimalStay.objects.get(pk=payload["stay_id"]).ends_on == date(2026, 2, 1)
    assert AnimalStay.objects.count() == 2


def test_non_center_unknown_species_and_overlap(api, user):
    center = Location.objects.create(code="C", name="Centro", kind="CENTRO")
    point = Location.objects.create(code="PV", name="Punto", kind="PUNTO_VENTA")
    species = Species.objects.create(code="BOVINO", name="Bovino")
    assign(user, "ADMIN")
    payload = animal_payload(point, species)
    assert api.post("/api/v1/animals", payload, format="json").status_code == 422
    payload["center_id"] = str(center.id)
    assert api.post("/api/v1/animals", payload, format="json").status_code == 200
    response = api.post(
        f"/api/v1/animals/{payload['id']}/stays",
        {
            "id": str(uuid.uuid4()),
            "center_id": str(center.id),
            "starts_on": "2026-01-02",
        },
        format="json",
    )
    assert response.status_code == 422
    assert AnimalStay.objects.count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_database_prevents_concurrent_overlapping_stays():
    species = Species.objects.create(code="BOVINO", name="Bovino")
    center = Location.objects.create(code="C", name="Centro", kind="CENTRO")
    animal = Animal.objects.create(code="V", species=species, sex="HEMBRA")
    barrier = Barrier(2)

    def insert():
        try:
            barrier.wait(timeout=10)
            with transaction.atomic():
                AnimalStay.objects.create(animal=animal, center=center, starts_on=date(2026, 1, 1))
            return "ok"
        except IntegrityError:
            return "conflict"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(insert) for _ in range(2)]
        assert sorted(future.result(timeout=15) for future in futures) == ["conflict", "ok"]
    assert AnimalStay.objects.count() == 1
