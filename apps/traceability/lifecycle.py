from django.utils import timezone
from rest_framework import serializers

from apps.accounts.access import require_role
from apps.audit.services import record
from apps.catalog.models import CenterProduct
from apps.common.errors import DomainError
from apps.common.serializers import StrictSerializer
from apps.common.services import check_version
from apps.notifications.services import notify
from apps.sync.serializers import EnvelopeSerializer

from .allocation import check_allocation
from .commands import lock_context, validate_draft
from .models import Conformity, ConformityDetail, Transfer
from .reads import transfer_data
from .serializers import TransferSerializer


class VersionPayload(StrictSerializer):
    version_id = serializers.UUIDField()


class TransferSendCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["TRANSFER_SEND"], default="TRANSFER_SEND")
    expected_version = serializers.IntegerField(min_value=1)
    payload = VersionPayload()


def authorize_producer(actor, command):
    transfer = (
        Transfer.objects.filter(pk=command["entity_id"]).select_related("current_version").first()
    )
    if transfer is None:
        raise DomainError("NOT_FOUND", "Entrega no disponible.", 404)
    require_role(actor, "PRODUCCION", transfer.current_version.origin_id)


def locked_transfer(command):
    _, transfer = lock_context(command["entity_id"], None)
    if transfer is None:
        raise DomainError("NOT_FOUND", "Entrega no disponible.", 404)
    check_version(transfer, command["expected_version"])
    return transfer


def ensure_document(transfer, version_id):
    if str(transfer.current_version_id) != str(version_id):
        raise DomainError("VERSION_CONFLICT", "El documento ya no está vigente.")


def validate_publication(actor, version):
    lines = list(version.lines.select_related("lot__production__current_version", "presentation"))
    if len(lines) != 1:
        raise DomainError("VALIDATION_ERROR", "El piloto requiere una línea por entrega.", 422)
    for line in lines:
        production = line.lot.production
        if not CenterProduct.objects.filter(
            center_id=production.center_id,
            product_id=production.product_id,
            enabled=True,
            product__active=True,
        ).exists():
            raise DomainError("VALIDATION_ERROR", "Producto no habilitado en el centro.", 422)
        _, quantity = validate_draft(
            actor,
            dict(
                destination_id=version.destination_id,
                driver_id=version.driver_id,
                receiver_id=version.receiver_id,
                presentation_id=line.presentation_id,
                units=line.units,
            ),
            line.lot,
        )
        if quantity != line.quantity:
            raise DomainError("VALIDATION_ERROR", "Cantidad incompatible con la presentación.", 422)
    check_allocation(lines, exclude_transfer=version.transfer_id)
    return lines


def sign(transfer, actor, operation, stage):
    version = transfer.current_version
    if (
        stage != "ENTREGA_ORIGEN"
        and Conformity.objects.filter(version__transfer=transfer, stage=stage).exists()
    ):
        raise DomainError("INVALID_STATE", "La etapa física ya fue confirmada.")
    conformity = Conformity.objects.create(
        version=version,
        user=actor,
        stage=stage,
        occurred_at=operation.occurred_at,
        operation=operation,
    )
    ConformityDetail.objects.bulk_create(
        [
            ConformityDetail(conformity=conformity, line=line, accepted_quantity=line.quantity)
            for line in version.lines.all()
        ]
    )
    return conformity


def finish(transfer, actor, operation, before, *, reason=""):
    transfer.lock_version += 1
    transfer.save()
    result = TransferSerializer(transfer_data(transfer, actor)).data
    record(
        actor,
        "transfer",
        transfer.id,
        operation.type,
        before=before,
        after=result,
        reason=reason,
        operation=operation,
    )
    return result


def send(actor, command, operation):
    transfer = locked_transfer(command)
    require_role(actor, "PRODUCCION", transfer.current_version.origin_id)
    if transfer.state != "BORRADOR":
        raise DomainError("INVALID_STATE", "Solo se envía un borrador.")
    ensure_document(transfer, command["payload"]["version_id"])
    before = transfer_data(transfer, actor)
    version = transfer.current_version
    validate_publication(actor, version)
    version.state, version.published_at = "PUBLICADA", timezone.now()
    version.save()
    transfer.state = "PENDIENTE_RECOGIDA"
    sign(transfer, actor, operation, "ENTREGA_ORIGEN")
    notify(
        recipients=[version.driver_id],
        type="PICKUP_REQUESTED",
        source_event_id=operation.event_id,
        entity_type="transfer",
        entity_id=transfer.id,
        version_id=version.id,
    )
    return finish(transfer, actor, operation, before)


def lifecycle_commands():
    return {"TRANSFER_SEND": (TransferSendCommand, send, authorize_producer)}
