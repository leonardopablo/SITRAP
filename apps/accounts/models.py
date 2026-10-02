import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils import timezone


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    password_change_required = models.BooleanField(default=False)


class Role(models.Model):
    class Code(models.TextChoices):
        PRODUCCION = "PRODUCCION"
        TRANSPORTE = "TRANSPORTE"
        RECEPCION = "RECEPCION"
        ADMIN = "ADMIN"

    code = models.CharField(primary_key=True, max_length=16, choices=Code.choices)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(code__in=["PRODUCCION", "TRANSPORTE", "RECEPCION", "ADMIN"]),
                name="role_known_code",
            ),
        ]


class RoleAssignment(models.Model):
    class Scope(models.TextChoices):
        GLOBAL = "GLOBAL"
        UBICACION = "UBICACION"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="assignments")
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    scope = models.CharField(max_length=12, choices=Scope.choices)
    location = models.ForeignKey(
        "catalog.Location", null=True, blank=True, on_delete=models.PROTECT
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(scope="GLOBAL", location__isnull=True, role_id="ADMIN")
                    | Q(scope="UBICACION", location__isnull=False)
                ),
                name="assignment_scope_valid",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gt=models.F("starts_at")),
                name="assignment_period_valid",
            ),
            models.UniqueConstraint(
                fields=["user", "role", "scope", "location"],
                condition=Q(ends_at__isnull=True, scope="UBICACION"),
                name="assignment_open_location_unique",
            ),
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=Q(ends_at__isnull=True, scope="GLOBAL"),
                name="assignment_open_global_unique",
            ),
        ]


class LoginBucket(models.Model):
    key = models.CharField(primary_key=True, max_length=64)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
