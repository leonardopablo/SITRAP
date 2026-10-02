import uuid

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
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


class Animal(models.Model):
    class Sex(models.TextChoices):
        HEMBRA = "HEMBRA"
        MACHO = "MACHO"

    class Status(models.TextChoices):
        ACTIVO = "ACTIVO"
        INACTIVO = "INACTIVO"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    species = models.ForeignKey(Species, on_delete=models.PROTECT)
    sex = models.CharField(max_length=8, choices=Sex.choices)
    name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVO)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(sex__in=["HEMBRA", "MACHO"]), name="animal_sex_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["ACTIVO", "INACTIVO"]), name="animal_status_valid"
            ),
        ]


class AnimalStay(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    animal = models.ForeignKey(Animal, on_delete=models.PROTECT, related_name="stays")
    center = models.ForeignKey(Location, on_delete=models.PROTECT)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_on__isnull=True) | Q(ends_on__gt=models.F("starts_on")),
                name="animal_stay_period_valid",
            ),
            ExclusionConstraint(
                name="animal_stays_no_overlap",
                expressions=[
                    ("animal", RangeOperators.EQUAL),
                    (
                        models.Func(
                            "starts_on",
                            "ends_on",
                            models.Value("[)"),
                            function="DATERANGE",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]
