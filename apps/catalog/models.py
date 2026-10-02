import uuid

from django.db import models
from django.db.models import Q


class Location(models.Model):
    class Kind(models.TextChoices):
        CENTRO = "CENTRO"
        PUNTO_VENTA = "PUNTO_VENTA"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["CENTRO", "PUNTO_VENTA"]), name="location_kind_valid"
            ),
        ]
