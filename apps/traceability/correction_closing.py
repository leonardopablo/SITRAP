from django.utils import timezone
from rest_framework import serializers

from apps.accounts.access import require_role
from apps.common.errors import DomainError
from apps.notifications.services import notify
from apps.sync.serializers import EnvelopeSerializer

from .correction_models import Correction, CorrectionDecision
from .corrections import correction_data
from .decisions import (
    approver_function,
    authorize_decision,
    finish_correction,
    locked_correction,
    persist_correction,
)
from .lifecycle import VersionPayload, finish
from .reads import transfer_data
from .revision import ReasonPayload


class RejectPayload(VersionPayload):
    reason = serializers.CharField(max_length=2000)


class CorrectionRejectCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["CORRECTION_REJECT"], default="CORRECTION_REJECT")
    expected_version = serializers.IntegerField(min_value=1)
    payload = RejectPayload()


class CorrectionWithdrawCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["CORRECTION_WITHDRAW"], default="CORRECTION_WITHDRAW")
    expected_version = serializers.IntegerField(min_value=1)
    payload = ReasonPayload()


def authorize_withdraw(actor, command):
    correction = (
        Correction.objects.filter(pk=command["entity_id"])
        .select_related("original_version")
        .first()
    )
    if correction is None:
        raise DomainError("NOT_FOUND", "Solicitud no disponible.", 404)
    require_role(actor, "PRODUCCION", correction.original_version.origin_id)
    if actor.id != correction.requester_id:
        raise DomainError("PERMISSION_DENIED", "Solo retira la propuesta su solicitante.", 403)


def close(actor, command, operation):
    correction, transfer = locked_correction(command)
    withdrawing = command["type"] == "CORRECTION_WITHDRAW"
    before, transfer_before = correction_data(correction, actor), transfer_data(transfer, actor)
    reason = command["payload"]["reason"]
    if withdrawing:
        authorize_withdraw(actor, command)
    else:
        function = approver_function(actor, correction)
        if correction.decisions.filter(function=function).exists():
            raise DomainError("INVALID_STATE", "La función ya emitió su decisión.")
        CorrectionDecision.objects.create(
            correction=correction,
            function=function,
            user=actor,
            decision="RECHAZAR",
            reason=reason,
            decided_at=operation.occurred_at,
            operation=operation,
        )
    proposed = correction.proposed_version
    proposed.state = "RETIRADA"
    proposed.save(update_fields=["state"])
    correction.state = "RETIRADA" if withdrawing else "RECHAZADA"
    correction.finished_at = timezone.now()
    persist_correction(correction)
    finish(transfer, actor, operation, transfer_before, reason=reason)
    recipients = [correction.transport_approver_id, correction.reception_approver_id]
    if not withdrawing:
        recipients.append(correction.requester_id)
    notify(
        recipients=recipients,
        type="CORRECTION_WITHDRAWN" if withdrawing else "CORRECTION_REJECTED",
        source_event_id=operation.event_id,
        entity_type="correction",
        entity_id=correction.id,
        version_id=proposed.id,
    )
    return finish_correction(correction, actor, operation, before, reason=reason)


def closing_commands():
    return {
        "CORRECTION_REJECT": (CorrectionRejectCommand, close, authorize_decision),
        "CORRECTION_WITHDRAW": (CorrectionWithdrawCommand, close, authorize_withdraw),
    }
