from django.utils import timezone
from rest_framework import serializers

from apps.accounts.access import require_role
from apps.audit.services import record
from apps.catalog.quantities import presentation_quantity
from apps.common.errors import DomainError
from apps.common.services import check_version
from apps.notifications.services import notify
from apps.sync.serializers import EnvelopeSerializer

from .allocation import check_allocation
from .commands import lock_context
from .correction_models import Correction, CorrectionDecision
from .corrections import CorrectionSerializer, correction_data
from .lifecycle import VersionPayload, finish
from .reads import transfer_data


class CorrectionAcceptCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["CORRECTION_ACCEPT"], default="CORRECTION_ACCEPT")
    expected_version = serializers.IntegerField(min_value=1)
    payload = VersionPayload()


def approver_function(actor, correction):
    version = correction.original_version
    if actor.pk == correction.transport_approver_id:
        require_role(actor, "TRANSPORTE", version.origin_id)
        return "TRANSPORTE"
    if actor.pk == correction.reception_approver_id:
        require_role(actor, "RECEPCION", version.destination_id)
        return "RECEPCION"
    raise DomainError("PERMISSION_DENIED", "Solo decide un aprobador fijado.", 403)


def authorize_decision(actor, command):
    correction = (
        Correction.objects.filter(pk=command["entity_id"])
        .select_related("original_version")
        .first()
    )
    if correction is None:
        raise DomainError("NOT_FOUND", "Solicitud no disponible.", 404)
    approver_function(actor, correction)


def locked_correction(command):
    reference = Correction.objects.get(pk=command["entity_id"])
    _, transfer = lock_context(reference.transfer_id, None)
    correction = Correction.objects.select_for_update().get(pk=reference.pk)
    correction.transfer = transfer
    check_version(correction, command["expected_version"])
    if correction.state != "PENDIENTE":
        raise DomainError("INVALID_STATE", "La solicitud ya fue resuelta.")
    if transfer.current_version_id != correction.original_version_id:
        raise DomainError("VERSION_CONFLICT", "Cambió el documento original.")
    if (
        "version_id" in command["payload"]
        and str(correction.proposed_version_id) != command["payload"]["version_id"]
    ):
        raise DomainError("VERSION_CONFLICT", "La propuesta no coincide.")
    return correction, transfer


def persist_correction(correction):
    correction.lock_version += 1
    correction.save(update_fields=["lock_version", "state", "finished_at"])


def finish_correction(correction, actor, operation, before, *, reason=""):
    result = CorrectionSerializer(correction_data(correction, actor)).data
    record(
        actor,
        "correction",
        correction.id,
        operation.type,
        before=before,
        after=result,
        reason=reason,
        operation=operation,
    )
    return result


def accept(actor, command, operation):
    correction, transfer = locked_correction(command)
    function = approver_function(actor, correction)
    before = correction_data(correction, actor)
    if correction.decisions.filter(function=function).exists():
        raise DomainError("INVALID_STATE", "La función ya emitió su decisión.")
    CorrectionDecision.objects.create(
        correction=correction,
        function=function,
        user=actor,
        decision="ACEPTAR",
        decided_at=operation.occurred_at,
        operation=operation,
    )
    applied = correction.decisions.filter(decision="ACEPTAR").count() == 2
    if applied:
        original, proposed = correction.original_version, correction.proposed_version
        require_role(correction.transport_approver, "TRANSPORTE", original.origin_id)
        require_role(correction.reception_approver, "RECEPCION", original.destination_id)
        lines = list(
            proposed.lines.select_related(
                "lot__production__current_version", "presentation__product"
            )
        )
        for line in lines:
            if (
                presentation_quantity(line.presentation, line.units, milk_pilot=True)
                != line.quantity
            ):
                raise DomainError("VALIDATION_ERROR", "Presentación incompatible.", 422)
        check_allocation(lines, exclude_transfer=transfer.id)
        transfer_before = transfer_data(transfer, actor)
        original.state = "SUPERADA"
        original.save(update_fields=["state"])
        proposed.state, proposed.published_at = "PUBLICADA", timezone.now()
        proposed.save(update_fields=["state", "published_at"])
        transfer.current_version = proposed
        correction.state, correction.finished_at = "APLICADA", timezone.now()
        persist_correction(correction)
        finish(transfer, actor, operation, transfer_before, reason=correction.reason)
        recipients = [
            correction.requester_id,
            correction.transport_approver_id,
            correction.reception_approver_id,
        ]
    else:
        persist_correction(correction)
        recipients = [
            correction.requester_id,
            correction.reception_approver_id
            if function == "TRANSPORTE"
            else correction.transport_approver_id,
        ]
    notify(
        recipients=recipients,
        type="CORRECTION_APPLIED" if applied else "CORRECTION_PROGRESS",
        source_event_id=operation.event_id,
        entity_type="correction",
        entity_id=correction.id,
        version_id=correction.proposed_version_id,
    )
    return finish_correction(correction, actor, operation, before)


def decision_commands():
    return {"CORRECTION_ACCEPT": (CorrectionAcceptCommand, accept, authorize_decision)}
