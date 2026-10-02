import uuid

from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    entity_type = models.CharField(max_length=40)
    entity_id = models.UUIDField()
    action = models.CharField(max_length=60)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    operation = models.ForeignKey("sync.SyncOperation", null=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["operation", "entity_type", "entity_id", "action"],
                name="audit_operation_action_unique",
            ),
        ]
