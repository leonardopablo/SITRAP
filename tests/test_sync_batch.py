import uuid

import pytest

from apps.milk.models import Milking
from apps.sync.models import SyncOperation
from tests.test_milking_confirm import complete_command, confirm_command
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db


def post(user, events):
    return client_for(user).post("/api/v1/sync/events", {"events": events}, format="json")


def chain(user):
    create = complete_command(user)
    create["type"] = "MILKING_CREATE"
    confirm = confirm_command(create)
    confirm["depends_on"] = [create["event_id"]]
    return create, confirm


def test_unordered_batch_is_topological_and_idempotent(user):
    create, confirm = chain(user)
    response = post(user, [confirm, create])
    assert response.status_code == 200, response.data
    assert [r["status"] for r in response.json()["results"]] == ["APLICADA", "APLICADA"]
    assert post(user, [confirm, create]).json() == response.json()
    assert Milking.objects.get().production.state == "CONFIRMADA"


def test_missing_parent_waits_and_arrival_resumes_without_rewriting(user):
    create, confirm = chain(user)
    response = post(user, [confirm])
    assert response.status_code == 200, response.data
    assert response.json()["results"][0]["status"] == "ESPERA_DEPENDENCIA"
    response = post(user, [create])
    assert response.json()["reprocessed"][0]["event_id"] == confirm["event_id"]
    assert response.json()["reprocessed"][0]["status"] == "APLICADA"


def test_cycles_and_malformed_payload_reject_before_any_effect(user):
    create, confirm = chain(user)
    create["depends_on"] = [confirm["event_id"]]
    assert post(user, [create, confirm]).status_code == 422
    assert not SyncOperation.objects.exists()
    create["depends_on"] = []
    confirm["payload"]["free_liters"] = "8"
    assert post(user, [create, confirm]).status_code == 422
    assert not Milking.objects.exists()


def test_business_rejection_propagates_and_online_only_rejected(user):
    create, confirm = chain(user)
    create["payload"]["details"][0]["animal_id"] = str(uuid.uuid4())
    response = post(user, [confirm, create])
    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["error"]["code"] == "DEPENDENCY_REJECTED"
    assert results[1]["status"] == "RECHAZADA"
    online = {
        **create,
        "type": "MILKING_VOID",
        "payload": {"reason": "test"},
        "expected_version": 1,
    }
    assert post(user, [online]).status_code == 422


def test_missing_timestamp_zone_rejected(user):
    create, _ = chain(user)
    create["occurred_at"] = "2026-10-02T08:00:00"
    assert post(user, [create]).status_code == 422


def test_cycle_spanning_batches_is_rejected(user):
    create, confirm = chain(user)
    create["depends_on"] = [confirm["event_id"]]
    assert post(user, [create]).json()["results"][0]["status"] == "ESPERA_DEPENDENCIA"
    assert post(user, [confirm]).status_code == 422
    assert not SyncOperation.objects.filter(pk=confirm["event_id"]).exists()


def test_unrelated_dependency_cannot_authorize_another_entity(user):
    create, _ = chain(user)
    assert post(user, [create]).status_code == 200
    other = {
        **create,
        "event_id": str(uuid.uuid4()),
        "entity_id": str(uuid.uuid4()),
        "depends_on": [create["event_id"]],
    }
    response = post(user, [other])
    assert response.json()["results"][0]["error"]["code"] == "DEPENDENCY_UNRELATED"
    assert Milking.objects.count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_concurrent_batches_cannot_persist_a_dependency_cycle():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import connections

    from apps.accounts.models import User

    actor = User.objects.create_user(username="producer")
    create, first = chain(actor)
    second = confirm_command(create)
    first["depends_on"], second["depends_on"] = [second["event_id"]], [first["event_id"]]
    barrier = Barrier(2)

    def run(event):
        try:
            barrier.wait(timeout=10)
            return post(actor, [event]).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, event) for event in [first, second]]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 422]
    assert SyncOperation.objects.count() == 1
