import uuid

from django.conf import settings
from django.db import models


class Device(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    prepared_at = models.DateTimeField(null=True)
    preparation_expires_at = models.DateTimeField(null=True)
    last_contact_at = models.DateTimeField(auto_now=True)


class SyncOperation(models.Model):
    class State(models.TextChoices):
        RECIBIDA = "RECIBIDA"
        ESPERA_DEPENDENCIA = "ESPERA_DEPENDENCIA"
        APLICADA = "APLICADA"
        RECHAZADA = "RECHAZADA"

    event_id = models.UUIDField(primary_key=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    device = models.ForeignKey(Device, on_delete=models.PROTECT)
    type = models.CharField(max_length=40)
    entity_id = models.UUIDField()
    expected_version = models.PositiveIntegerField(null=True)
    payload_hash = models.CharField(max_length=64)
    payload = models.JSONField()
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=24, choices=State.choices, default=State.RECIBIDA)
    response = models.JSONField(default=dict)
    http_status = models.PositiveSmallIntegerField(default=200)

    class Meta:
        indexes = [models.Index(fields=["user", "state"])]


class SyncDependency(models.Model):
    operation = models.ForeignKey(
        SyncOperation, on_delete=models.PROTECT, related_name="dependencies"
    )
    depends_on_event_id = models.UUIDField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "depends_on_event_id"], name="operation_dependency_unique"
            )
        ]
