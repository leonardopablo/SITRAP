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


class Unit(models.Model):
    code = models.CharField(
        primary_key=True, max_length=3, choices=[("L", "L"), ("KG", "KG"), ("UN", "UN")]
    )
    name = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(code__in=["L", "KG", "UN"]), name="unit_code_valid")
        ]


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=150)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)


class CenterProduct(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    center = models.ForeignKey(Location, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["center", "product"], name="center_product_unique")
        ]


class Presentation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    content_base = models.DecimalField(max_digits=14, decimal_places=3)
    allows_fraction = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(content_base__gt=0), name="presentation_content_positive"
            )
        ]


class Species(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)


class Turn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
