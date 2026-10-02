import uuid

from django.db import models


class Lot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    production = models.OneToOneField(
        "production.Production", on_delete=models.PROTECT, related_name="lot"
    )
    code = models.CharField(max_length=48, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
