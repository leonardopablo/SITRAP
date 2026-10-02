import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Lot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production = models.OneToOneField(
        "production.Production", on_delete=models.PROTECT, related_name="lot"
    )
    code = models.CharField(max_length=48, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Transfer(models.Model):
    class State(models.TextChoices):
        BORRADOR = "BORRADOR"
        PENDIENTE_RECOGIDA = "PENDIENTE_RECOGIDA"
        EN_CAMINO = "EN_CAMINO"
        RECIBIDO = "RECIBIDO"
        CANCELADO = "CANCELADO"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=48, unique=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    state = models.CharField(max_length=24, choices=State.choices, default=State.BORRADOR)
    current_version = models.ForeignKey(
        "TransferVersion", null=True, on_delete=models.PROTECT, related_name="+"
    )
    lock_version = models.PositiveIntegerField(default=1)


class TransferVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(Transfer, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    origin = models.ForeignKey("catalog.Location", on_delete=models.PROTECT, related_name="+")
    destination = models.ForeignKey("catalog.Location", on_delete=models.PROTECT, related_name="+")
    emitter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    state = models.CharField(
        max_length=16,
        choices=[
            (value, value)
            for value in ("BORRADOR", "PROPUESTA", "PUBLICADA", "SUPERADA", "RETIRADA")
        ],
        default="BORRADOR",
    )
    reason = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transfer", "number"], name="transfer_version_number_unique"
            )
        ]


class TransferLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(TransferVersion, on_delete=models.PROTECT, related_name="lines")
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT)
    presentation = models.ForeignKey("catalog.Presentation", on_delete=models.PROTECT)
    units = models.DecimalField(max_digits=14, decimal_places=3)
    content_base_snapshot = models.DecimalField(max_digits=14, decimal_places=3)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "lot", "presentation"], name="transfer_line_unique"
            ),
            models.CheckConstraint(
                condition=Q(units__gt=0, content_base_snapshot__gt=0, quantity__gt=0),
                name="transfer_line_positive",
            ),
        ]


class Conformity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(
        TransferVersion, on_delete=models.PROTECT, related_name="conformities"
    )
    stage = models.CharField(
        max_length=24,
        choices=[(value, value) for value in ("ENTREGA_ORIGEN", "RECOGIDA", "RECEPCION")],
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    occurred_at = models.DateTimeField()
    registered_at = models.DateTimeField(auto_now_add=True)
    operation = models.ForeignKey("sync.SyncOperation", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["version", "stage"], name="version_conformity_stage_unique"
            )
        ]


class ConformityDetail(models.Model):
    conformity = models.ForeignKey(Conformity, on_delete=models.PROTECT, related_name="details")
    line = models.ForeignKey(TransferLine, on_delete=models.PROTECT)
    accepted_quantity = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conformity", "line"], name="conformity_detail_unique")
        ]
