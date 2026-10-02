import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Correction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        "traceability.Transfer", on_delete=models.PROTECT, related_name="corrections"
    )
    original_version = models.ForeignKey(
        "traceability.TransferVersion", on_delete=models.PROTECT, related_name="+"
    )
    proposed_version = models.OneToOneField(
        "traceability.TransferVersion", on_delete=models.PROTECT, related_name="+"
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.TextField()
    transport_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reception_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    state = models.CharField(
        max_length=16,
        choices=[(v, v) for v in ["PENDIENTE", "APLICADA", "RECHAZADA", "RETIRADA"]],
        default="PENDIENTE",
    )
    lock_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transfer"], condition=Q(state="PENDIENTE"), name="one_pending_correction"
            ),
            models.CheckConstraint(
                condition=~Q(transport_approver=F("reception_approver")),
                name="correction_distinct_approvers",
            ),
        ]


class CorrectionDecision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    correction = models.ForeignKey(Correction, on_delete=models.PROTECT, related_name="decisions")
    function = models.CharField(
        max_length=16, choices=[(v, v) for v in ["TRANSPORTE", "RECEPCION"]]
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=16, choices=[(v, v) for v in ["ACEPTAR", "RECHAZAR"]])
    reason = models.TextField(blank=True)
    decided_at = models.DateTimeField()
    registered_at = models.DateTimeField(auto_now_add=True)
    operation = models.ForeignKey("sync.SyncOperation", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["correction", "function"], name="one_decision_per_function"
            ),
            models.CheckConstraint(
                condition=~Q(decision="RECHAZAR") | ~Q(reason=""), name="rejection_requires_reason"
            ),
        ]
