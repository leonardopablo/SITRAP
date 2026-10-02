from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import serializers

from apps.accounts.access import is_admin, location_ids, require_role
from apps.audit.services import record
from apps.common.errors import DomainError
from apps.common.serializers import StrictSerializer
from apps.notifications.services import notify
from apps.sync.serializers import EnvelopeSerializer

from .allocation import check_allocation
from .correction_models import Correction
from .lifecycle import authorize_producer, finish, locked_transfer
from .models import Conformity
from .reads import transfer_data, version_data
from .revision import clone_document
from .serializers import TransferVersionSerializer


class CorrectionPayload(StrictSerializer):
    correction_id = serializers.UUIDField()
    version_id = serializers.UUIDField()
    line_id = serializers.UUIDField()
    units = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    reason = serializers.CharField(max_length=2000)


class CorrectionCreateCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["CORRECTION_CREATE"], default="CORRECTION_CREATE")
    expected_version = serializers.IntegerField(min_value=1)
    payload = CorrectionPayload()


class PendingApproverSerializer(serializers.Serializer):
    function = serializers.ChoiceField(choices=["TRANSPORTE", "RECEPCION"])
    user_id = serializers.UUIDField()


class DecisionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    function = serializers.ChoiceField(choices=["TRANSPORTE", "RECEPCION"])
    user_id = serializers.UUIDField()
    decision = serializers.ChoiceField(choices=["ACEPTAR", "RECHAZAR"])
    reason = serializers.CharField()
    decided_at = serializers.DateTimeField()
    registered_at = serializers.DateTimeField()


class CorrectionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    transfer_id = serializers.UUIDField()
    transfer_lock_version = serializers.IntegerField()
    state = serializers.ChoiceField(choices=["PENDIENTE", "APLICADA", "RECHAZADA", "RETIRADA"])
    lock_version = serializers.IntegerField()
    requester_id = serializers.UUIDField()
    reason = serializers.CharField()
    transport_approver_id = serializers.UUIDField()
    reception_approver_id = serializers.UUIDField()
    original_version = TransferVersionSerializer()
    proposed_version = TransferVersionSerializer()
    created_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)
    decisions = DecisionSerializer(many=True)
    pending_approvers = PendingApproverSerializer(many=True)
    capabilities = serializers.ListField(child=serializers.CharField())


class CorrectionCreatedSerializer(serializers.Serializer):
    transfer_id = serializers.UUIDField()
    lock_version = serializers.IntegerField()
    correction = CorrectionSerializer()


def scoped_corrections(actor):
    queryset = Correction.objects.select_related("transfer", "original_version", "proposed_version")
    if is_admin(actor):
        return queryset
    return queryset.filter(
        Q(original_version__origin_id__in=location_ids(actor, "PRODUCCION"))
        | Q(
            transport_approver=actor,
            original_version__origin_id__in=location_ids(actor, "TRANSPORTE"),
        )
        | Q(
            reception_approver=actor,
            original_version__destination_id__in=location_ids(actor, "RECEPCION"),
        )
    )


def correction_data(correction, actor):
    return {
        "id": correction.id,
        "transfer_id": correction.transfer_id,
        "transfer_lock_version": correction.transfer.lock_version,
        "state": correction.state,
        "lock_version": correction.lock_version,
        "requester_id": correction.requester_id,
        "reason": correction.reason,
        "transport_approver_id": correction.transport_approver_id,
        "reception_approver_id": correction.reception_approver_id,
        "original_version": version_data(correction.original_version),
        "proposed_version": version_data(correction.proposed_version),
        "created_at": correction.created_at,
        "finished_at": correction.finished_at,
        "decisions": list(
            correction.decisions.order_by("registered_at", "id").values(
                "id", "function", "user_id", "decision", "reason", "decided_at", "registered_at"
            )
        ),
        "pending_approvers": [
            {"function": role, "user_id": user_id}
            for role, user_id in [
                ("TRANSPORTE", correction.transport_approver_id),
                ("RECEPCION", correction.reception_approver_id),
            ]
            if not correction.decisions.filter(function=role).exists()
        ]
        if correction.state == "PENDIENTE"
        else [],
        "capabilities": correction_capabilities(correction, actor),
    }


def create_correction(actor, command, operation):
    transfer = locked_transfer(command)
    authorize_producer(actor, command)
    if transfer.state not in ["EN_CAMINO", "RECIBIDO"]:
        raise DomainError("INVALID_STATE", "Solo se corrigen cantidades después de recogida.")
    if transfer.corrections.filter(state="PENDIENTE").exists():
        raise DomainError("CORRECTION_PENDING", "Ya existe una propuesta pendiente.")
    payload = CorrectionPayload(data=command["payload"])
    payload.is_valid(raise_exception=True)
    data = payload.validated_data
    old = transfer.current_version
    pickup = (
        Conformity.objects.filter(version__transfer=transfer, stage="RECOGIDA")
        .select_related("user")
        .first()
    )
    reception = (
        Conformity.objects.filter(version__transfer=transfer, stage="RECEPCION")
        .select_related("user")
        .first()
    )
    if pickup is None:
        raise DomainError("INVALID_STATE", "Falta la conformidad física de recogida.")
    driver = pickup.user
    receiver = reception.user if reception else old.receiver
    if driver.pk == receiver.pk:
        raise DomainError("VALIDATION_ERROR", "Se requieren dos aprobadores diferentes.", 422)
    require_role(driver, "TRANSPORTE", old.origin_id)
    require_role(receiver, "RECEPCION", old.destination_id)
    if data["units"] % 1:
        raise DomainError("VALIDATION_ERROR", "La bolsa es indivisible.", 422)
    before = transfer_data(transfer, actor)
    proposed = clone_document(
        old,
        version_id=data["version_id"],
        line_id=data["line_id"],
        units=data["units"],
        reason=data["reason"],
        emitter=old.emitter,
    )
    check_allocation(
        list(proposed.lines.select_related("lot__production__current_version")),
        exclude_transfer=transfer.id,
    )
    proposed.state = "PROPUESTA"
    proposed.save(update_fields=["state"])
    try:
        with transaction.atomic():
            correction = Correction.objects.create(
                id=data["correction_id"],
                transfer=transfer,
                original_version=old,
                proposed_version=proposed,
                requester=actor,
                reason=data["reason"],
                transport_approver=driver,
                reception_approver=receiver,
            )
    except IntegrityError:
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de solicitud ya utilizado.")
    notify(
        recipients=[driver.id, receiver.id],
        type="CORRECTION_REQUESTED",
        source_event_id=operation.event_id,
        entity_type="correction",
        entity_id=correction.id,
        version_id=proposed.id,
    )
    finish(transfer, actor, operation, before, reason=data["reason"])
    result = CorrectionCreatedSerializer(
        {
            "transfer_id": transfer.id,
            "lock_version": transfer.lock_version,
            "correction": correction_data(correction, actor),
        }
    ).data
    record(
        actor,
        "correction",
        correction.id,
        "CORRECTION_CREATE",
        after=result["correction"],
        reason=data["reason"],
        operation=operation,
    )
    return result


def correction_commands():
    return {"CORRECTION_CREATE": (CorrectionCreateCommand, create_correction, authorize_producer)}


def correction_capabilities(correction, actor):
    from .decisions import approver_function

    if correction.state != "PENDIENTE":
        return []
    result = []
    if (
        correction.requester_id == actor.id
        and correction.original_version.origin_id in location_ids(actor, "PRODUCCION")
    ):
        result.append("withdraw")
    try:
        function = approver_function(actor, correction)
    except DomainError:
        return result
    if not correction.decisions.filter(function=function).exists():
        result += ["accept", "reject"]
    return result
