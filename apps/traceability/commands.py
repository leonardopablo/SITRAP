from decimal import Decimal

from django.db import IntegrityError, transaction
from rest_framework import serializers

from apps.accounts.access import require_role
from apps.accounts.options import assignable_users
from apps.audit.services import record
from apps.catalog.models import Location, Presentation
from apps.catalog.quantities import presentation_quantity
from apps.common.errors import DomainError
from apps.common.serializers import StrictSerializer
from apps.common.services import check_version, lock_rows
from apps.production.models import Production
from apps.sync.serializers import EnvelopeSerializer
from apps.traceability.models import Lot, Transfer, TransferLine, TransferVersion
from apps.traceability.reads import transfer_data
from apps.traceability.serializers import TransferSerializer


class DraftPayload(StrictSerializer):
    version_id = serializers.UUIDField()
    line_id = serializers.UUIDField()
    lot_id = serializers.UUIDField()
    presentation_id = serializers.UUIDField()
    units = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal("0.001"))
    destination_id = serializers.UUIDField()
    driver_id = serializers.UUIDField()
    receiver_id = serializers.UUIDField()


class TransferCreateCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["TRANSFER_CREATE"], default="TRANSFER_CREATE")
    payload = DraftPayload()

    def validate(self, data):
        data = super().validate(data)
        if data.get("expected_version") is not None:
            raise serializers.ValidationError({"expected_version": "No se envía en una creación."})
        return data


class TransferUpdateCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["TRANSFER_UPDATE"], default="TRANSFER_UPDATE")
    expected_version = serializers.IntegerField(min_value=1)
    payload = DraftPayload()


def authorize_transfer(actor, command):
    if command["type"] != "TRANSFER_CREATE":
        transfer = (
            Transfer.objects.filter(pk=command["entity_id"])
            .select_related("current_version")
            .first()
        )
        if transfer is None:
            raise DomainError("NOT_FOUND", "Entrega no disponible.", 404)
        require_role(actor, "PRODUCCION", transfer.current_version.origin_id)
    lot = Lot.objects.filter(pk=command["payload"]["lot_id"]).select_related("production").first()
    if lot is None:
        raise DomainError("VALIDATION_ERROR", "Lote no disponible.", 422)
    require_role(actor, "PRODUCCION", lot.production.center_id)


def lock_context(transfer_id, incoming_lot_id):
    old_lots = set(
        TransferLine.objects.filter(
            version__transfer_id=transfer_id,
            version_id__in=Transfer.objects.filter(pk=transfer_id).values("current_version_id"),
        ).values_list("lot_id", flat=True)
    )
    lot_ids = old_lots | {incoming_lot_id}
    production_ids = Lot.objects.filter(pk__in=lot_ids).values_list("production_id", flat=True)
    lock_rows(Production, production_ids)
    lots = {lot.pk: lot for lot in lock_rows(Lot, lot_ids)}
    transfer = Transfer.objects.select_for_update().filter(pk=transfer_id).first()
    if transfer:
        current_lots = set(transfer.current_version.lines.values_list("lot_id", flat=True))
        if not current_lots.issubset(lot_ids):
            raise DomainError("VERSION_CONFLICT", "La entrega cambió; vuelva a consultarla.")
    return lots[incoming_lot_id], transfer


def validate_draft(actor, data, lot):
    production = lot.production
    if production.state != "CONFIRMADA":
        raise DomainError("INVALID_STATE", "El lote no procede de una producción confirmada.")
    require_role(actor, "PRODUCCION", production.center_id)
    if not Location.objects.filter(
        pk=data["destination_id"], kind="PUNTO_VENTA", active=True
    ).exists():
        raise DomainError("VALIDATION_ERROR", "Destino no habilitado.", 422)
    if (
        not assignable_users("TRANSPORTE", production.center_id)
        .filter(pk=data["driver_id"])
        .exists()
    ):
        raise DomainError("VALIDATION_ERROR", "Conductor sin asignación vigente.", 422)
    if (
        not assignable_users("RECEPCION", data["destination_id"])
        .filter(pk=data["receiver_id"])
        .exists()
    ):
        raise DomainError("VALIDATION_ERROR", "Receptor sin asignación vigente.", 422)
    if data["driver_id"] == data["receiver_id"]:
        raise DomainError(
            "VALIDATION_ERROR", "Transporte y recepción requieren cuentas diferentes.", 422
        )
    presentation = (
        Presentation.objects.select_related("product")
        .filter(pk=data["presentation_id"], product_id=production.product_id)
        .first()
    )
    if presentation is None:
        raise DomainError("VALIDATION_ERROR", "Presentación incompatible con el lote.", 422)
    quantity = presentation_quantity(presentation, data["units"], milk_pilot=True)
    return presentation, quantity


def draft_handler(actor, command, operation):
    serializer = DraftPayload(data=command["payload"])
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    lot, transfer = lock_context(command["entity_id"], data["lot_id"])
    creating = command["type"] == "TRANSFER_CREATE"
    if creating and transfer:
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de entrega ya utilizado.")
    if not creating:
        check_version(transfer, command["expected_version"])
        if transfer.state != "BORRADOR":
            raise DomainError("INVALID_STATE", "Solo se edita un borrador.")
        if transfer.current_version_id != data["version_id"]:
            raise DomainError("VERSION_CONFLICT", "Documento borrador obsoleto.")
    presentation, quantity = validate_draft(actor, data, lot)
    before = transfer_data(transfer, actor) if transfer else {}
    try:
        with transaction.atomic():
            if creating:
                transfer = Transfer.objects.create(
                    id=command["entity_id"],
                    code=f"T-{command['entity_id'].replace('-', '')}",
                    creator=actor,
                )
                version = TransferVersion(id=data["version_id"], transfer=transfer, number=1)
            else:
                version = transfer.current_version
                version.lines.all().delete()
                transfer.lock_version += 1
            version.origin_id = lot.production.center_id
            version.destination_id = data["destination_id"]
            version.emitter = actor
            version.driver_id = data["driver_id"]
            version.receiver_id = data["receiver_id"]
            version.save()
            TransferLine.objects.create(
                id=data["line_id"],
                version=version,
                lot=lot,
                presentation=presentation,
                units=data["units"],
                content_base_snapshot=presentation.content_base,
                quantity=quantity,
            )
            transfer.current_version = version
            transfer.save()
    except IntegrityError:
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de documento o línea ya utilizado.")
    result = TransferSerializer(transfer_data(transfer, actor)).data
    record(
        actor,
        "transfer",
        transfer.id,
        command["type"],
        before=before,
        after=result,
        operation=operation,
    )
    return result


def transfer_commands():
    return {
        "TRANSFER_CREATE": (TransferCreateCommand, draft_handler, authorize_transfer),
        "TRANSFER_UPDATE": (TransferUpdateCommand, draft_handler, authorize_transfer),
    }
