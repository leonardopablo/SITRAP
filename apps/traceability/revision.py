from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework import serializers

from apps.common.errors import DomainError
from apps.common.serializers import StrictSerializer
from apps.notifications.services import notify
from apps.sync.serializers import EnvelopeSerializer

from .lifecycle import authorize_producer, finish, locked_transfer, sign, validate_publication
from .models import Conformity, TransferLine, TransferVersion
from .reads import transfer_data


class RevisePayload(StrictSerializer):
    version_id = serializers.UUIDField()
    line_id = serializers.UUIDField()
    units = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    destination_id = serializers.UUIDField()
    driver_id = serializers.UUIDField()
    receiver_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=2000)


class ReasonPayload(StrictSerializer):
    reason = serializers.CharField(max_length=2000)


class TransferReviseCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["TRANSFER_REVISE"], default="TRANSFER_REVISE")
    expected_version = serializers.IntegerField(min_value=1)
    payload = RevisePayload()


class TransferCancelCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["TRANSFER_CANCEL"], default="TRANSFER_CANCEL")
    expected_version = serializers.IntegerField(min_value=1)
    payload = ReasonPayload()


def clone_document(source, *, version_id, line_id, units, reason, emitter, **changes):
    source_line = source.lines.get()
    number = source.transfer.versions.aggregate(last=Max("number"))["last"] + 1
    try:
        with transaction.atomic():
            version = TransferVersion.objects.create(
                id=version_id,
                transfer=source.transfer,
                number=number,
                origin_id=source.origin_id,
                destination_id=changes.get("destination_id", source.destination_id),
                emitter=emitter,
                driver_id=changes.get("driver_id", source.driver_id),
                receiver_id=changes.get("receiver_id", source.receiver_id),
                reason=reason,
            )
            TransferLine.objects.create(
                id=line_id,
                version=version,
                lot=source_line.lot,
                presentation=source_line.presentation,
                units=units,
                content_base_snapshot=source_line.content_base_snapshot,
                quantity=Decimal(units) * source_line.content_base_snapshot,
            )
    except IntegrityError:
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de documento o línea ya utilizado.")
    return version


def require_before_pickup(transfer, states):
    if (
        transfer.state not in states
        or Conformity.objects.filter(version__transfer=transfer, stage="RECOGIDA").exists()
    ):
        raise DomainError("INVALID_STATE", "La entrega ya no permite cambios antes de recogida.")


def revise(actor, command, operation):
    transfer = locked_transfer(command)
    authorize_producer(actor, command)
    require_before_pickup(transfer, ["PENDIENTE_RECOGIDA"])
    before = transfer_data(transfer, actor)
    previous = transfer.current_version
    data = RevisePayload(data=command["payload"])
    data.is_valid(raise_exception=True)
    version = clone_document(previous, emitter=actor, **data.validated_data)
    validate_publication(actor, version)
    previous.state = "SUPERADA"
    previous.save(update_fields=["state"])
    version.state, version.published_at = "PUBLICADA", timezone.now()
    version.save(update_fields=["state", "published_at"])
    transfer.current_version = version
    sign(transfer, actor, operation, "ENTREGA_ORIGEN")
    notify(
        recipients=[previous.driver_id, version.driver_id],
        type="PICKUP_REQUEST_UPDATED",
        source_event_id=operation.event_id,
        entity_type="transfer",
        entity_id=transfer.id,
        version_id=version.id,
    )
    return finish(transfer, actor, operation, before, reason=version.reason)


def cancel(actor, command, operation):
    transfer = locked_transfer(command)
    authorize_producer(actor, command)
    require_before_pickup(transfer, ["BORRADOR", "PENDIENTE_RECOGIDA"])
    before = transfer_data(transfer, actor)
    if transfer.state == "PENDIENTE_RECOGIDA":
        notify(
            recipients=[transfer.current_version.driver_id],
            type="TRANSFER_CANCELLED",
            source_event_id=operation.event_id,
            entity_type="transfer",
            entity_id=transfer.id,
            version_id=transfer.current_version_id,
        )
    transfer.state = "CANCELADO"
    return finish(transfer, actor, operation, before, reason=command["payload"]["reason"])


def revision_commands():
    return {
        "TRANSFER_REVISE": (TransferReviseCommand, revise, authorize_producer),
        "TRANSFER_CANCEL": (TransferCancelCommand, cancel, authorize_producer),
    }
