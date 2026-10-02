import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Production(models.Model):
    class State(models.TextChoices):
        BORRADOR = "BORRADOR"
        CONFIRMADA = "CONFIRMADA"
        ANULADA = "ANULADA"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    center = models.ForeignKey("catalog.Location", on_delete=models.PROTECT)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    type = models.CharField(max_length=16, default="MILK")
    state = models.CharField(max_length=16, choices=State.choices, default=State.BORRADOR)
    current_version = models.ForeignKey(
        "ProductionVersion", on_delete=models.PROTECT, null=True, related_name="+"
    )
    lock_version = models.PositiveIntegerField(default=1)


class ProductionVersion(models.Model):
    class State(models.TextChoices):
        BORRADOR = "BORRADOR"
        PUBLICADA = "PUBLICADA"
        SUPERADA = "SUPERADA"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production = models.ForeignKey(Production, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    state = models.CharField(max_length=16, choices=State.choices, default=State.BORRADOR)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["production", "number"], name="production_version_number_unique"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=0), name="production_quantity_nonnegative"
            ),
        ]
