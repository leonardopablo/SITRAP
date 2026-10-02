import uuid

from django.db import models
from django.db.models import Q


class Milking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production = models.OneToOneField(
        "production.Production", on_delete=models.PROTECT, related_name="milking"
    )
    center = models.ForeignKey("catalog.Location", on_delete=models.PROTECT)
    date = models.DateField()
    turn = models.ForeignKey("catalog.Turn", on_delete=models.PROTECT)
    voided_at = models.DateTimeField(null=True)
    replaces = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, related_name="replacements"
    )


class MilkingDetail(models.Model):
    version = models.ForeignKey(
        "production.ProductionVersion", on_delete=models.PROTECT, related_name="details"
    )
    animal = models.ForeignKey("catalog.Animal", on_delete=models.PROTECT)
    liters = models.DecimalField(max_digits=14, decimal_places=3, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "animal"], name="milking_version_animal_unique"
            ),
            models.CheckConstraint(
                condition=Q(liters__isnull=True) | Q(liters__gte=0),
                name="milking_liters_nonnegative",
            ),
        ]
