from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from apps.audit.services import record
from apps.common.errors import DomainError
from apps.common.serializers import StrictSerializer
from apps.common.services import check_version
from apps.production.models import Production, ProductionVersion
from apps.sync.serializers import EnvelopeSerializer
from apps.traceability.allocation import reserved_quantities
from apps.traceability.models import Lot

from .models import Milking, MilkingDetail
from .serializers import CowDetail
from .services import authorize_milking, milking_data, parse_payload
from .voiding import void_internal


class RectifyPayload(StrictSerializer):
    version_id = serializers.UUIDField()
    details = CowDetail(many=True, max_length=500, allow_empty=False)
    reason = serializers.CharField(max_length=2000)


class VoidPayload(StrictSerializer):
    reason = serializers.CharField(max_length=2000)


class MilkingRectifyCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["MILKING_RECTIFY"], default="MILKING_RECTIFY")
    expected_version = serializers.IntegerField(min_value=1)
    payload = RectifyPayload()


class MilkingVoidCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["MILKING_VOID"], default="MILKING_VOID")
    expected_version = serializers.IntegerField(min_value=1)
    payload = VoidPayload()


def rectify(actor, command, operation):
    data = parse_payload(RectifyPayload, command["payload"])
    reference = Milking.objects.get(pk=command["entity_id"])
    production = Production.objects.select_for_update().get(pk=reference.production_id)
    lots = list(Lot.objects.select_for_update().filter(production=production).order_by("id"))
    milking = Milking.objects.select_for_update().get(pk=reference.id)
    milking.production = production
    check_version(production, command["expected_version"])
    authorize_milking(actor, command)
    if production.state != "CONFIRMADA":
        raise DomainError("INVALID_STATE", "Solo se rectifica una producción confirmada.")
    old = production.current_version
    original_cows = set(old.details.values_list("animal_id", flat=True))
    rows = data["details"]
    ids = [row["animal_id"] for row in rows]
    if (
        len(ids) != len(set(ids))
        or set(ids) != original_cows
        or any(row["liters"] is None for row in rows)
    ):
        raise DomainError(
            "VALIDATION_ERROR", "Complete exactamente las vacas del documento original.", 422
        )
    quantity = sum((row["liters"] for row in rows), Decimal(0))
    if not Decimal(0) < quantity <= Decimal("99999999999.999"):
        raise DomainError("VALIDATION_ERROR", "Total positivo fuera de rango.", 422)
    reservations = reserved_quantities()
    if quantity < sum((reservations[lot.id] for lot in lots), Decimal(0)):
        raise DomainError(
            "ALLOCATION_EXCEEDED", "La producción debe cubrir las asignaciones máximas."
        )
    before = milking_data(milking, actor)
    try:
        with transaction.atomic():
            version = ProductionVersion.objects.create(
                id=data["version_id"],
                production=production,
                number=old.number + 1,
                quantity=quantity,
                author=actor,
                reason=data["reason"],
            )
            MilkingDetail.objects.bulk_create(
                [MilkingDetail(version=version, **row) for row in rows]
            )
            version.state, version.published_at = "PUBLICADA", timezone.now()
            version.save(update_fields=["state", "published_at"])
            old.state = "SUPERADA"
            old.save(update_fields=["state"])
            production.current_version = version
            production.lock_version += 1
            production.save(update_fields=["current_version", "lock_version"])
    except IntegrityError:
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de versión ya utilizado.")
    result = milking_data(milking, actor)
    record(
        actor,
        "production",
        production.id,
        "MILKING_RECTIFY",
        before=before,
        after=result,
        reason=data["reason"],
        operation=operation,
    )
    return result


def void(actor, command, operation):
    return void_internal(
        actor,
        command["entity_id"],
        command["expected_version"],
        command["payload"]["reason"],
        operation=operation,
    )


def rectification_commands():
    return {
        "MILKING_RECTIFY": (MilkingRectifyCommand, rectify, authorize_milking),
        "MILKING_VOID": (MilkingVoidCommand, void, authorize_milking),
    }
