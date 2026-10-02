from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.access import (
    capabilities,
    is_admin,
    require_assigned,
    require_role,
    scoped_get,
    scoped_queryset,
)
from apps.accounts.models import RoleAssignment, User
from apps.catalog.models import Location
from apps.common.errors import DomainError

pytestmark = pytest.mark.django_db


def assign(user, role, location=None, **kwargs):
    return RoleAssignment.objects.create(
        user=user,
        role_id=role,
        location=location,
        scope="UBICACION" if location else "GLOBAL",
        **kwargs,
    )


def test_scopes_deny_other_center_and_id(user, api):
    own = Location.objects.create(code="A", name="A", kind="CENTRO")
    other = Location.objects.create(code="B", name="B", kind="CENTRO")
    assign(user, "PRODUCCION", own)
    require_role(user, "PRODUCCION", own.id)
    with pytest.raises(DomainError):
        require_role(user, "PRODUCCION", other.id)
    queryset = scoped_queryset(Location.objects.all(), user, "PRODUCCION", "id")
    assert list(queryset) == [own]
    with pytest.raises(NotFound):
        scoped_get(queryset, id=other.id)
    data = api.get("/api/v1/auth/me").json()
    assert [item["id"] for item in data["locations"]] == [str(own.id)]
    assert all(item["location_id"] == str(own.id) for item in data["capabilities"])


def test_admin_read_does_not_grant_operator_actions(user):
    location = Location.objects.create(code="A", name="A", kind="CENTRO")
    assign(user, "ADMIN")
    assert is_admin(user)
    assert scoped_queryset(Location.objects.all(), user, "PRODUCCION", "id").exists()
    with pytest.raises(DomainError):
        require_role(user, "TRANSPORTE", location.id)
    assert "pickup" not in {item["code"] for item in capabilities(user)}
    assign(user, "TRANSPORTE", location)
    require_assigned(user, "TRANSPORTE", location.id, user.id)
    other = User.objects.create_user(username="other")
    with pytest.raises(DomainError):
        require_assigned(user, "TRANSPORTE", location.id, other.id)


def test_revoked_future_and_inactive_scopes(user):
    location = Location.objects.create(code="A", name="A", kind="CENTRO")
    assignment = assign(user, "PRODUCCION", location, starts_at=timezone.now() + timedelta(days=1))
    with pytest.raises(DomainError):
        require_role(user, "PRODUCCION", location.id)
    assignment.starts_at = timezone.now() - timedelta(days=2)
    assignment.ends_at = timezone.now() - timedelta(days=1)
    assignment.save()
    with pytest.raises(DomainError):
        require_role(user, "PRODUCCION", location.id)
    assignment.ends_at = None
    assignment.save()
    location.active = False
    location.save()
    with pytest.raises(DomainError):
        require_role(user, "PRODUCCION", location.id)
    location.active = True
    location.save()
    User.objects.filter(pk=user.pk).update(is_active=False)
    with pytest.raises(DomainError):
        require_role(user, "PRODUCCION", location.id)


def test_superuser_is_not_a_business_role(user):
    user.is_superuser = True
    user.save()
    assert not is_admin(user)


def test_temporary_password_blocks_domain_but_allows_account(user, api):
    user.password_change_required = True
    user.save()
    assert api.get("/api/v1/auth/me").status_code == 200
    assert api.get("/api/v1/auth/me").json()["capabilities"] == []
    response = api.get("/api/v1/schema")
    assert response.status_code == 403 and response.data["code"] == "PASSWORD_CHANGE_REQUIRED"
