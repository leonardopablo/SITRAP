from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import RoleAssignment
from apps.sync.models import Device, SyncSnapshot
from apps.traceability.models import Transfer
from tests.test_transfer_reads import client_for
from tests.test_transfer_receive import in_transit

pytestmark = pytest.mark.django_db(transaction=True)


def download(client, device, path="/api/v1/sync/bootstrap", query=None):
    results = []
    response = client.get(path, query or {}, HTTP_X_DEVICE_ID=str(device.id))
    assert response.status_code == 200, response.data
    body = response.json()
    results.extend(body["results"])
    while body["next_page"]:
        response = client.get(
            path, {"page": body["next_page"], "limit": 3}, HTTP_X_DEVICE_ID=str(device.id)
        )
        assert response.status_code == 200, response.data
        body = response.json()
        results.extend(body["results"])
    return results, body["cursor"]


def test_bootstrap_paging_scope_and_revocation_tombstones(user):
    _, transfer = in_transit(user)
    driver = transfer.current_version.driver
    device = Device.objects.get(user=driver, name="physical")
    client = client_for(driver)
    # Open work remains regardless of its age.
    Transfer.objects.filter(pk=transfer.pk).update(code="OLD-OPEN")
    from unittest.mock import patch

    with patch("apps.sync.snapshots.timezone", wraps=timezone) as clock:
        clock.now.return_value = timezone.now() + timedelta(days=60)
        rows, cursor = download(client, device, query={"limit": 3})
    types = {row["entity_type"] for row in rows}
    assert {"transfer", "lot", "conformity", "timeline", "notification", "me"} <= types
    assert "animal" not in types and "milking" not in types
    assert len(rows) == len({(r["entity_type"], r["id"]) for r in rows})
    RoleAssignment.objects.filter(user=driver).delete()
    changes, _ = download(client, device, "/api/v1/sync/changes", {"cursor": cursor})
    assert any(
        r["entity_type"] == "transfer" and r["id"] == str(transfer.id) and r["deleted"]
        for r in changes
    )
    assert not any(r["entity_type"] == "transfer" and not r["deleted"] for r in changes)
    device.refresh_from_db()
    assert device.preparation_expires_at > timezone.now()


def test_expired_foreign_cursor_and_mid_page_revocation(user):
    _, transfer = in_transit(user)
    driver = transfer.current_version.driver
    device = Device.objects.get(user=driver, name="physical")
    client = client_for(driver)
    initial = client.get(
        "/api/v1/sync/bootstrap", {"limit": 1}, HTTP_X_DEVICE_ID=str(device.id)
    ).json()
    other = Device.objects.create(user=user, name="other")
    assert (
        client_for(user)
        .get(
            "/api/v1/sync/bootstrap", {"page": initial["next_page"]}, HTTP_X_DEVICE_ID=str(other.id)
        )
        .status_code
        == 422
    )
    RoleAssignment.objects.filter(user=driver).delete()
    assert (
        client.get(
            "/api/v1/sync/bootstrap",
            {"page": initial["next_page"]},
            HTTP_X_DEVICE_ID=str(device.id),
        ).status_code
        == 409
    )
    _, cursor = download(client, device)
    SyncSnapshot.objects.filter(device=device).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    response = client.get(
        "/api/v1/sync/changes", {"cursor": cursor}, HTTP_X_DEVICE_ID=str(device.id)
    )
    assert response.status_code == 410 and response.json()["code"] == "CURSOR_EXPIRED"


def test_catalog_deactivation_is_an_explicit_tombstone(user):
    from apps.catalog.models import Turn

    _, transfer = in_transit(user)
    device = Device.objects.filter(user=user).first()
    client = client_for(user)
    rows, cursor = download(client, device)
    turn = Turn.objects.get()
    assert any(r["entity_type"] == "turn" and r["id"] == str(turn.id) for r in rows)
    turn.active = False
    turn.save()
    changes, _ = download(client, device, "/api/v1/sync/changes", {"cursor": cursor})
    assert any(
        r["entity_type"] == "turn" and r["id"] == str(turn.id) and r["deleted"] for r in changes
    )
