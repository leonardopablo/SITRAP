import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import RoleAssignment, User
from apps.audit.models import AuditEntry
from apps.catalog.models import Location
from tests.test_access import assign

pytestmark = pytest.mark.django_db


def make_admin(user):
    assign(user, "ADMIN")


def test_only_admin_and_no_privilege_injection(api, user):
    assert api.get("/api/v1/users").status_code == 403
    assert api.post("/api/v1/role-assignments", {}, format="json").status_code == 403
    make_admin(user)
    response = api.post(
        "/api/v1/users",
        {
            "id": str(uuid.uuid4()),
            "username": "receptor",
            "name": "R",
            "temporary_password": "Temporary-strong-123!",
            "is_superuser": True,
        },
        format="json",
    )
    assert response.status_code == 422


def test_create_reset_deactivate_and_audit(api, user):
    make_admin(user)
    payload = {
        "id": str(uuid.uuid4()),
        "username": "receptor",
        "name": "Receptora",
        "temporary_password": "Temporary-strong-123!",
    }
    response = api.post("/api/v1/users", payload, format="json")
    assert response.status_code == 200, response.data
    assert "temporary_password" not in response.json()
    assert response.json()["password_change_required"]
    assert api.post("/api/v1/users", payload, format="json").status_code == 200
    assert AuditEntry.objects.filter(action="CREATE_USER").count() == 1
    target_id = response.json()["id"]
    assert (
        api.post(
            f"/api/v1/users/{target_id}/reset-password",
            {"temporary_password": "Another-temporary-123!"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        api.post(
            f"/api/v1/users/{target_id}/reset-password",
            {"temporary_password": "Another-temporary-123!"},
            format="json",
        ).status_code
        == 200
    )
    assert AuditEntry.objects.filter(action="RESET_PASSWORD").count() == 1
    assert (
        api.patch(f"/api/v1/users/{target_id}", {"is_active": False}, format="json").status_code
        == 200
    )
    assert not User.objects.get(pk=target_id).is_active
    assert all("Temporary-strong" not in str(item.after) for item in AuditEntry.objects.all())


def test_assignments_validate_scopes_overlap_and_preserve_history(api, user):
    make_admin(user)
    target = User.objects.create_user(username="production", name="P")
    center = Location.objects.create(code="C1", name="Centro", kind="CENTRO")
    start = timezone.now() - timedelta(days=1)
    payload = {
        "id": str(uuid.uuid4()),
        "user_id": str(target.id),
        "role": "PRODUCCION",
        "scope": "GLOBAL",
        "location_id": None,
        "starts_at": start.isoformat(),
    }
    assert api.post("/api/v1/role-assignments", payload, format="json").status_code == 422
    payload.update(scope="UBICACION", location_id=str(center.id))
    response = api.post("/api/v1/role-assignments", payload, format="json")
    assert response.status_code == 200, response.data
    assert api.post("/api/v1/role-assignments", payload, format="json").status_code == 200
    duplicate = {
        **payload,
        "id": str(uuid.uuid4()),
        "ends_at": (timezone.now() + timedelta(days=1)).isoformat(),
    }
    assert api.post("/api/v1/role-assignments", duplicate, format="json").status_code == 422
    role_id = response.json()["id"]
    assert (
        api.patch(
            f"/api/v1/role-assignments/{role_id}", {"role": "ADMIN"}, format="json"
        ).status_code
        == 422
    )
    assert (
        api.patch(
            f"/api/v1/role-assignments/{role_id}",
            {"ends_at": timezone.now().isoformat()},
            format="json",
        ).status_code
        == 200
    )
    assert RoleAssignment.objects.get(pk=role_id).ends_at is not None


def test_reset_revokes_session_and_deactivation_denies_me(api, user):
    from rest_framework.test import APIClient

    make_admin(user)
    target = User.objects.create_user(username="target", name="T", password="Original-strong-123!")
    client = APIClient()
    client.force_login(target)
    assert client.get("/api/v1/auth/me").status_code == 200
    assert (
        api.post(
            f"/api/v1/users/{target.id}/reset-password",
            {"temporary_password": "Temporary-strong-123!"},
            format="json",
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/me").status_code == 401
    client.force_login(target)
    assert (
        api.patch(f"/api/v1/users/{target.id}", {"is_active": False}, format="json").status_code
        == 200
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_bootstrap_first_admin_only(monkeypatch):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    monkeypatch.setenv("SITRAP_BOOTSTRAP_PASSWORD", "Bootstrap-strong-123!")
    call_command("bootstrap_admin", username="initial", name="Initial Admin")
    assert RoleAssignment.objects.get().role_id == "ADMIN"
    assert User.objects.get().password_change_required
    with pytest.raises(CommandError):
        call_command("bootstrap_admin", username="another", name="Another Admin")
