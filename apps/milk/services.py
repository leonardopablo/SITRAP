from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.access import is_admin, location_ids, require_role
from apps.audit.services import record
from apps.catalog.models import Animal, AnimalStay, CenterProduct, Turn
from apps.common.errors import DomainError
from apps.common.services import check_version
from apps.milk.models import Milking, MilkingDetail
from apps.milk.serializers import MilkingConfirmPayload, MilkingCreatePayload, MilkingUpdatePayload
from apps.production.models import Production, ProductionVersion
from apps.traceability.models import Lot


def scoped_milkings(actor):
    query = Milking.objects.select_related("production__current_version", "production__product")
    return (
        query if is_admin(actor) else query.filter(center_id__in=location_ids(actor, "PRODUCCION"))
    )


def eligible_cows(center_id, date):
    stays = AnimalStay.objects.filter(center_id=center_id, starts_on__lte=date).filter(
        Q(ends_on__isnull=True) | Q(ends_on__gt=date)
    )
    return Animal.objects.filter(pk__in=stays.values("animal_id"), status="ACTIVO", sex="HEMBRA")


def milking_data(milking, actor):
    production = milking.production
    version = production.current_version
    details = list(version.details.order_by("animal_id").values("animal_id", "liters"))
    eligible = set(eligible_cows(milking.center_id, milking.date).values_list("id", flat=True))
    complete = (
        bool(details)
        and all(row["liters"] is not None for row in details)
        and eligible == {row["animal_id"] for row in details}
    )
    allowed = []
    if production.state == "BORRADOR" and milking.center_id in location_ids(actor, "PRODUCCION"):
        allowed = ["update", "confirm"]
    return {
        "id": str(milking.id),
        "replaces_id": str(milking.replaces_id) if milking.replaces_id else None,
        "voided_at": milking.voided_at.isoformat() if milking.voided_at else None,
        "lot_id": str(lot_id)
        if (
            lot_id := Lot.objects.filter(production=production).values_list("id", flat=True).first()
        )
        else None,
        "production_id": str(production.id),
        "product_id": str(production.product_id),
        "center_id": str(milking.center_id),
        "responsible_id": str(production.responsible_id),
        "date": milking.date.isoformat(),
        "turn_id": str(milking.turn_id),
        "state": production.state,
        "lock_version": production.lock_version,
        "version_id": str(version.id),
        "version_number": version.number,
        "quantity": f"{version.quantity:.3f}",
        "details": [
            {
                "animal_id": str(row["animal_id"]),
                "liters": None if row["liters"] is None else f"{row['liters']:.3f}",
            }
            for row in details
        ],
        "complete": complete,
        "capabilities": allowed,
    }


def authorize_milking(actor, command):
    if command["type"] == "MILKING_CREATE":
        require_role(actor, "PRODUCCION", command["payload"]["center_id"])
    else:
        milking = Milking.objects.filter(pk=command["entity_id"]).first()
        if milking is None:
            raise DomainError("NOT_FOUND", "Ordeño no disponible.", 404)
        require_role(actor, "PRODUCCION", milking.center_id)


def validate_details(center_id, date, turn_id, rows):
    if not Turn.objects.filter(pk=turn_id, active=True).exists():
        raise DomainError("VALIDATION_ERROR", "Turno no habilitado.", 422)
    ids = [row["animal_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise DomainError("VALIDATION_ERROR", "No repita una vaca.", 422)
    eligible = set(eligible_cows(center_id, date).values_list("id", flat=True))
    if not set(ids).issubset(eligible):
        raise DomainError("VALIDATION_ERROR", "Vaca no disponible en el centro y fecha.", 422)
    quantity = sum((row["liters"] for row in rows if row["liters"] is not None), Decimal("0"))
    if quantity > Decimal("99999999999.999"):
        raise DomainError("VALIDATION_ERROR", "Total fuera de rango.", 422)
    return quantity


def parse_payload(serializer_class, payload):
    serializer = serializer_class(data=payload)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def create_milking(actor, command, operation):
    data = parse_payload(MilkingCreatePayload, command["payload"])
    link = CenterProduct.objects.filter(
        center_id=data["center_id"],
        product_id=data["product_id"],
        enabled=True,
        center__active=True,
        center__kind="CENTRO",
        product__active=True,
        product__unit_id="L",
    ).first()
    if link is None:
        raise DomainError("VALIDATION_ERROR", "Producto en litros no habilitado en el centro.", 422)
    if data.get("replaces_id"):
        previous = Milking.objects.filter(
            pk=data["replaces_id"],
            center_id=data["center_id"],
            production__product_id=data["product_id"],
        ).first()
        if previous is None:
            raise DomainError("VALIDATION_ERROR", "Referencia de reemplazo no válida.", 422)
        previous_production = Production.objects.select_for_update().get(pk=previous.production_id)
        previous.refresh_from_db()
        if previous_production.state != "ANULADA" or previous.voided_at is None:
            raise DomainError("INVALID_STATE", "Primero debe anular la producción anterior.")
    quantity = validate_details(data["center_id"], data["date"], data["turn_id"], data["details"])
    if Milking.objects.filter(
        center_id=data["center_id"],
        date=data["date"],
        turn_id=data["turn_id"],
        voided_at__isnull=True,
    ).exists():
        raise DomainError(
            "INVALID_STATE", "Ya existe un ordeño no anulado para ese centro, fecha y turno."
        )
    try:
        with transaction.atomic():
            production = Production.objects.create(
                id=data["production_id"],
                product_id=data["product_id"],
                center_id=data["center_id"],
                responsible=actor,
            )
            version = ProductionVersion.objects.create(
                id=data["version_id"],
                production=production,
                number=1,
                quantity=quantity,
                author=actor,
            )
            production.current_version = version
            production.save(update_fields=["current_version"])
            milking = Milking.objects.create(
                id=command["entity_id"],
                replaces_id=data.get("replaces_id"),
                production=production,
                center_id=data["center_id"],
                date=data["date"],
                turn_id=data["turn_id"],
            )
            MilkingDetail.objects.bulk_create(
                [MilkingDetail(version=version, **row) for row in data["details"]]
            )
    except IntegrityError:
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID o combinación de ordeño ya utilizados.")
    result = milking_data(milking, actor)
    record(actor, "production", production.id, "CREATE_MILKING", after=result, operation=operation)
    return result


def locked_milking(command):
    reference = Milking.objects.get(pk=command["entity_id"])
    production = Production.objects.select_for_update().get(pk=reference.production_id)
    milking = Milking.objects.select_for_update().get(pk=reference.pk)
    milking.production = production
    check_version(production, command["expected_version"])
    return milking


def update_milking(actor, command, operation):
    data = parse_payload(MilkingUpdatePayload, command["payload"])
    milking = locked_milking(command)
    production = milking.production
    if production.state != "BORRADOR":
        raise DomainError("INVALID_STATE", "Solo se edita el borrador.")
    before = milking_data(milking, actor)
    quantity = validate_details(milking.center_id, data["date"], data["turn_id"], data["details"])
    if (
        Milking.objects.filter(
            center_id=milking.center_id,
            date=data["date"],
            turn_id=data["turn_id"],
            voided_at__isnull=True,
        )
        .exclude(pk=milking.pk)
        .exists()
    ):
        raise DomainError("INVALID_STATE", "Centro, fecha y turno ya utilizados.")
    milking.date, milking.turn_id = data["date"], data["turn_id"]
    try:
        with transaction.atomic():
            milking.save(update_fields=["date", "turn"])
    except IntegrityError:
        raise DomainError("INVALID_STATE", "Centro, fecha y turno ya utilizados.")
    version = production.current_version
    version.details.all().delete()
    MilkingDetail.objects.bulk_create(
        [MilkingDetail(version=version, **row) for row in data["details"]]
    )
    version.quantity = quantity
    version.save(update_fields=["quantity"])
    production.lock_version += 1
    production.save(update_fields=["lock_version"])
    result = milking_data(milking, actor)
    record(
        actor,
        "production",
        production.id,
        "UPDATE_MILKING",
        before=before,
        after=result,
        operation=operation,
    )
    return result


def confirm_milking(actor, command, operation):
    data = parse_payload(MilkingConfirmPayload, command["payload"])
    milking = locked_milking(command)
    production = milking.production
    if production.state != "BORRADOR":
        raise DomainError("INVALID_STATE", "La producción ya no es borrador.")
    version = production.current_version
    if version.id != data["version_id"]:
        raise DomainError("VERSION_CONFLICT", "Documento de producción obsoleto.")
    before = milking_data(milking, actor)
    rows = list(version.details.values("animal_id", "liters"))
    quantity = validate_details(milking.center_id, milking.date, milking.turn_id, rows)
    if not before["complete"] or quantity <= 0:
        raise DomainError(
            "VALIDATION_ERROR", "Complete cada vaca y registre un total positivo.", 422
        )
    if not CenterProduct.objects.filter(
        center_id=milking.center_id,
        product_id=production.product_id,
        enabled=True,
        product__active=True,
        center__active=True,
    ).exists():
        raise DomainError("VALIDATION_ERROR", "Producto o centro ya no habilitado.", 422)
    try:
        with transaction.atomic():
            Lot.objects.create(
                id=data["lot_id"],
                production=production,
                code=f"L-{milking.date:%Y%m%d}-{data['lot_id'].hex}",
            )
    except IntegrityError:
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de lote ya utilizado.")
    version.quantity = quantity
    version.state = "PUBLICADA"
    version.published_at = timezone.now()
    version.save(update_fields=["quantity", "state", "published_at"])
    production.state = "CONFIRMADA"
    production.lock_version += 1
    production.save(update_fields=["state", "lock_version"])
    result = milking_data(milking, actor)
    record(
        actor,
        "production",
        production.id,
        "CONFIRM_MILKING",
        before=before,
        after=result,
        operation=operation,
    )
    return result
