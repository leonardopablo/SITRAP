import uuid

from django.conf import settings
from django.db import models


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
