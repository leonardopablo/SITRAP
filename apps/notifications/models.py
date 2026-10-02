import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    type = models.CharField(max_length=32)
    source_event_id = models.UUIDField()
    entity_type = models.CharField(max_length=32)
    entity_id = models.UUIDField()
    version_id = models.UUIDField(null=True)
    title = models.CharField(max_length=160)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "source_event_id", "type"],
                name="notification_event_recipient_unique",
            )
        ]
        indexes = [models.Index(fields=["recipient", "-created_at", "-id"])]


class PushSubscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    device = models.ForeignKey("sync.Device", on_delete=models.PROTECT)
    endpoint = models.CharField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=128)
    auth = models.CharField(max_length=64)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True)


class PushDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification, on_delete=models.PROTECT, related_name="deliveries"
    )
    subscription = models.ForeignKey(PushSubscription, on_delete=models.PROTECT)
    state = models.CharField(
        max_length=24,
        choices=[
            (v, v)
            for v in [
                "PENDIENTE",
                "PROCESANDO",
                "ACEPTADO_PROVEEDOR",
                "REINTENTABLE",
                "FALLIDO",
                "DESCARTADO",
            ]
        ],
        default="PENDIENTE",
    )
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_until = models.DateTimeField(null=True)
    lease_token = models.UUIDField(null=True)
    last_error = models.CharField(max_length=80, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "subscription"], name="one_push_per_subscription_event"
            )
        ]
        indexes = [models.Index(fields=["state", "next_attempt_at"])]
