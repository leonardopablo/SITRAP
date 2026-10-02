import uuid
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import Role, RoleAssignment, User
from apps.catalog.models import Location

pytestmark = pytest.mark.django_db


def test_uuid_user_and_seed_roles():
    user = User.objects.create_user(username="operator", password="a-secure-password")
    assert isinstance(user.id, uuid.UUID)
    assert user.check_password("a-secure-password")
    assert set(Role.objects.values_list("code", flat=True)) == set(Role.Code.values)


@pytest.mark.parametrize(
    "role,scope,has_location",
    [
        ("PRODUCCION", "GLOBAL", False),
        ("ADMIN", "GLOBAL", True),
        ("RECEPCION", "UBICACION", False),
        ("TRANSPORTE", "UNKNOWN", True),
    ],
)
def test_invalid_scope_database_constraint(role, scope, has_location):
    user = User.objects.create_user(username="operator")
    location = Location.objects.create(code="C1", name="Centro", kind="CENTRO")
    with pytest.raises(IntegrityError), transaction.atomic():
        RoleAssignment.objects.create(
            user=user,
            role_id=role,
            scope=scope,
            location=location if has_location else None,
        )


@pytest.mark.parametrize("scope,role", [("GLOBAL", "ADMIN"), ("UBICACION", "PRODUCCION")])
def test_unique_open_assignment_and_protected_history(scope, role):
    user = User.objects.create_user(username="operator")
    location = (
        Location.objects.create(code="C1", name="Centro", kind="CENTRO")
        if scope == "UBICACION"
        else None
    )
    fields = dict(user=user, role_id=role, scope=scope, location=location)
    assignment = RoleAssignment.objects.create(**fields)
    with pytest.raises(IntegrityError), transaction.atomic():
        RoleAssignment.objects.create(**fields)
    with pytest.raises(ProtectedError):
        user.delete()
    assignment.ends_at = timezone.now() + timedelta(seconds=1)
    assignment.save()
    # Closed history is retained when assigning again.
    RoleAssignment.objects.create(**fields, starts_at=assignment.ends_at)
    assert RoleAssignment.objects.count() == 2


def test_invalid_period_and_unknown_role_rejected_by_database():
    user = User.objects.create_user(username="operator")
    with pytest.raises(IntegrityError), transaction.atomic():
        RoleAssignment.objects.create(
            user=user,
            role_id="ADMIN",
            scope="GLOBAL",
            starts_at=timezone.now(),
            ends_at=timezone.now() - timedelta(days=1),
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Role.objects.create(code="SUPERADMIN")
