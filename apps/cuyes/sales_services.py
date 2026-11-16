from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.access import require_admin, require_role
from apps.accounts.models import User
from apps.audit.services import record, snapshot

from .access import enabled_centers, require_pen, require_shed, sheds_for
from .locking import lock_centers
from .models import (
    BreedingModule,
    DispatchSelection,
    ModuleComponent,
    PaymentEvidence,
    ReservationDetail,
    SaleConformity,
    SaleDelivery,
    SaleDispatch,
    SaleDispatchDetail,
    SaleFinancialReview,
    SaleLine,
    SaleOrder,
    SalePayment,
    SalePreparation,
    SaleProposal,
    SaleReservation,
    SaleRevision,
    Shed,
)
from .sales_notifications import sale_notice
from .sales_serializers import SALE_COMMANDS
from .sales_stock import (
    available,
    claimed_buckets,
    demand,
    selection_missing,
    shortage_keys,
)
from .services import apply_lines, fail, get, line_snapshot, lock_scope, movement_for, occupation

PAID = ["PAGADO", "EN_PREPARACION"]
DISPATCHED = ["EN_RUTA", "EN_PUNTO", "ENTREGADO"]
ADMIN_ACTIONS = {
    "SALE_CREATE", "SALE_PROPOSAL_REVIEW", "SALE_PAY", "SALE_DRIVER", "SALE_COLLECT",
    "SALE_CANCEL", "SALE_WEIGH", "SALE_FINANCE", "SALE_RESOLVE_STOCK",
}


def worker_sheds(actor, order):
    return sheds_for(actor, operational=True).filter(center_id=order.center_id)


def require_worker(actor, order):
    require_role(actor, "GALPONERO", order.center_id)
    if not worker_sheds(actor, order).exists():
        fail("No tiene un galpón autorizado en el centro.", "PERMISSION_DENIED", 403)


def require_driver(actor, order):
    if order.mode != "PUNTO" or order.driver_id != actor.id:
        fail("Viaje no asignado a esta cuenta.", "PERMISSION_DENIED", 403)
    require_role(actor, "TRANSPORTE", order.center_id)


def authorize(actor, c):
    kind = c["type"]
    if kind in ADMIN_ACTIONS:
        require_admin(actor)
        return
    order = get(SaleOrder, c["entity_id"])
    if kind in ["SALE_PICKUP", "SALE_ARRIVE"]:
        require_driver(actor, order)
    else:
        require_worker(actor, order)


def lock_order(order_id):
    initial = get(SaleOrder, order_id)
    lock_centers([initial.center_id])
    # Same resource order as the inventory services; no stock is copied.
    list(Shed.objects.select_for_update().filter(center_id=initial.center_id).order_by("id"))
    return get(SaleOrder.objects.select_for_update(), order_id)


def expect_version(order, c):
    if c.get("expected_version") != order.version:
        fail("La orden cambió. Actualice y revise los datos antes de confirmar.", "VERSION_CONFLICT")


def require_state(order, states):
    if order.state not in states:
        fail(f"La acción no corresponde al estado {order.state}.")


def money(value):
    amount = Decimal(value).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
    if abs(amount) >= Decimal("1000000000000"):
        fail("El importe excede la precisión monetaria admitida.", "VALIDATION_ERROR", 422)
    return amount


def line_snapshot_data(line):
    return snapshot({
        "id": line.id, "kind": line.kind, "units": line.units, "animal_count": line.animal_count,
        "category": line.category, "quality": line.quality, "module_id": line.module_id,
        "recipe": line.recipe, "billing_unit": line.billing_unit, "weight_kg": line.weight_kg,
        "weight_basis": line.weight_basis, "unit_price": line.unit_price, "total": line.total,
    })


def revision(actor, order, action, reason, operation=None):
    order.version += 1
    order.reason = reason
    order.save()
    data = {
        "state": order.state, "version": order.version, "total": str(order.total),
        "preparation_id": str(order.preparation_id) if order.preparation_id else None,
        "lines": [line_snapshot_data(line) for line in order.lines.order_by("id")],
    }
    SaleRevision.objects.create(order=order, actor=actor, action=action, reason=reason, snapshot=data)
    record(actor, "cuy_sale", order.id, action, after=data, reason=reason, operation=operation)
    return {"order_id": str(order.id), "lock_version": order.version}


def reservation(order, *, live=False):
    obj = SaleReservation.objects.select_for_update().filter(order=order, state__in=["IMPAGA", "PAGADA"]).first()
    if not obj:
        fail("La orden no tiene una reserva vigente.", "RESERVATION_REQUIRED")
    if live and obj.state == "IMPAGA" and obj.expires_at <= timezone.now():
        fail("La reserva impaga venció. Debe confirmarse nuevamente.", "RESERVATION_EXPIRED")
    return obj


def release(reserve, state):
    reserve.state, reserve.released_at = state, timezone.now()
    reserve.save(update_fields=["state", "released_at"])


def expire_locked(actor, order, reserve):
    if reserve.state != "IMPAGA" or reserve.expires_at > timezone.now():
        return False
    release(reserve, "VENCIDA")
    order.state, order.preparation = "VENCIDO", None
    revision(actor, order, "SALE_EXPIRED", "Reserva impaga vencida por hora del servidor.")
    sale_notice(order, "SALE_EXPIRED", uuid5(NAMESPACE_URL, f"sale-expired:{reserve.id}"))
    return True


@transaction.atomic
def expire_one(actor, reserve_id):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    require_admin(actor)
    initial = get(SaleReservation, reserve_id)
    order = lock_order(initial.order_id)
    reserve = get(SaleReservation.objects.select_for_update(), reserve_id)
    return expire_locked(actor, order, reserve)


def make_line(order, p):
    kind = p["kind"]
    count = p["units"]
    if kind == "MODULO":
        if any(key in p for key in ["category", "quality", "weight_kg", "weight_basis"]):
            fail("Un módulo utiliza únicamente su receta copiada.", "VALIDATION_ERROR", 422)
        module = get(BreedingModule, p.get("module_id"))
        if not module.active:
            fail("Módulo inactivo.", "VALIDATION_ERROR", 422)
        recipe = list(module.components.order_by("category", "quality").values("category", "quality", "quantity"))
        if not recipe:
            fail("Módulo sin componentes.", "VALIDATION_ERROR", 422)
        if count * sum(i["quantity"] for i in recipe) > 1000000:
            fail("La orden supera el límite de animales por línea.", "VALIDATION_ERROR", 422)
        return SaleLine(
            id=p["id"], order=order, kind=kind, units=count,
            animal_count=count * sum(i["quantity"] for i in recipe), recipe=recipe,
            module=module, billing_unit="UN", unit_price=p["unit_price"],
            total=money(Decimal(p["unit_price"]) * count),
        )
    if p.get("module_id") or not p.get("category") or not p.get("quality"):
        fail("Seleccione categoría y calidad exactas.", "VALIDATION_ERROR", 422)
    weight = p.get("weight_kg")
    if kind == "PESO":
        if not weight or not p.get("weight_basis"):
            fail("Confirme peso en KG (3 decimales) y base de pesaje antes del pago.", "VALIDATION_ERROR", 422)
    elif weight or p.get("weight_basis"):
        fail("La venta por unidad no admite peso para el cobro.", "VALIDATION_ERROR", 422)
    return SaleLine(
        id=p["id"], order=order, kind=kind, units=count, animal_count=count,
        category=p["category"], quality=p["quality"], billing_unit="KG" if kind == "PESO" else "UN",
        weight_kg=weight, weight_basis=p.get("weight_basis", ""), unit_price=p["unit_price"],
        recipe=[{"category": p["category"], "quality": p["quality"], "quantity": 1}],
        total=money(Decimal(p["unit_price"]) * (Decimal(weight) if weight else count)),
    )


def check_demand(order, *, excluding_self=False):
    supply = available(order.center_id, exclude_order=order.id if excluding_self else None)
    if any(n > supply.get(key, 0) for key, n in demand(order).items()):
        fail("Faltan componentes para reservar la orden completa.", "INSUFFICIENT_AVAILABLE")


def validate_stock(order):
    if order.shortage or bool(shortage_keys(order.center_id) & set(demand(order))) or selection_missing(order):
        fail("Existencias comprometidas insuficientes. ADMIN debe revisar el faltante.", "SALE_STOCK_SHORTAGE")


def validate_plan(order, *, complete=True):
    if not order.preparation_id:
        fail("Falta seleccionar las pozas de origen.", "SELECTION_REQUIRED")
    totals, buckets = defaultdict(int), defaultdict(int)
    rows = list(order.preparation.selections.select_related("line", "occupation__lot", "occupation__pen__shed__center"))
    if not rows and complete:
        fail("La preparación está vacía.", "SELECTION_REQUIRED")
    for row in rows:
        if row.occupation.pen.shed.center_id != order.center_id:
            fail("La selección combina centros.", "VALIDATION_ERROR", 422)
        permitted = {(i["category"], i["quality"]): i["quantity"] * row.line.units for i in row.line.recipe}
        key = (row.category, row.quality)
        if key not in permitted:
            fail("La selección no coincide con sexo/calidad/receta acordados.", "SELECTION_MISMATCH")
        totals[(row.line_id, *key)] += row.quantity
        buckets[(row.occupation_id, *key)] += row.quantity
        pen = row.occupation.pen
        if not pen.active or not pen.shed.active:
            fail("Una poza de origen dejó de estar disponible.", "SELECTION_UNAVAILABLE")
    for line in order.lines.all():
        for component in line.recipe:
            actual = totals[(line.id, component["category"], component["quality"])]
            expected = line.units * component["quantity"]
            if actual > expected or (complete and actual != expected):
                fail("El detalle por poza no cuadra con todas las líneas reservadas.", "SELECTION_MISMATCH")
    from .models import Balance

    other = claimed_buckets(exclude_order=order.id)
    for (occ, category, quality), quantity in buckets.items():
        balance = Balance.objects.filter(occupation_id=occ, category=category, quality=quality).first()
        if not balance or balance.quantity - other.get((str(occ), category, quality), 0) < quantity:
            fail("Las mismas existencias ya fueron seleccionadas o cambiaron.", "SELECTION_UNAVAILABLE")
    return rows


def invalidate(order):
    order.confirmation_round += 1


def require_handoffs(order, rows, *, driver=True):
    confirmations = SaleConformity.objects.filter(preparation=order.preparation, round=order.confirmation_round)
    sheds = {row.occupation.pen.shed_id for row in rows}
    for shed_id in sheds:
        confirmation = confirmations.filter(stage="GALPONERO", shed_id=shed_id).first()
        if not confirmation:
            fail("Falta la conformidad de un galpón de origen.", "ORIGIN_CONFIRMATION_REQUIRED")
        require_shed(confirmation.actor, get(Shed, shed_id))
        require_role(confirmation.actor, "GALPONERO", order.center_id)
    if driver:
        confirmation = confirmations.filter(stage="CONDUCTOR", actor_id=order.driver_id).first()
        if not confirmation:
            fail("Falta la conformidad del conductor sobre este detalle.", "DRIVER_CONFIRMATION_REQUIRED")
        require_driver(confirmation.actor, order)


def physical_dispatch(actor, order, operation, reason, *, direct=False):
    require_state(order, PAID)
    if order.center_id not in enabled_centers():
        fail("Cuyes no está habilitado en el centro.")
    reserve = reservation(order, live=True)
    if reserve.state != "PAGADA" or order.financial_hold or order.approved_total != order.total:
        fail("El pago o el importe definitivo requieren revisión.", "FINANCIAL_REVIEW_REQUIRED")
    validate_stock(order)
    rows = validate_plan(order)
    require_handoffs(order, rows, driver=not direct)
    if not direct and order.mode != "PUNTO":
        fail("Recojo directo exige validar el PIN.")
    # The final origin registrar may only act on their own selected shed.
    own_sheds = set(worker_sheds(actor, order).values_list("id", flat=True))
    if not own_sheds & {r.occupation.pen.shed_id for r in rows}:
        fail("No participa en los orígenes seleccionados.", "PERMISSION_DENIED", 403)
    day = timezone.localdate()
    lock_scope([row.occupation.pen_id for row in rows], day)
    reserve.state, reserve.consumed_at = "CONSUMIDA", timezone.now()
    reserve.save(update_fields=["state", "consumed_at"])
    order.state = "ENTREGADO" if direct else "EN_RUTA"
    order.save()
    move = movement_for(actor, {
        "entity_id": str(operation.event_id), "type": "CUY_SALE_DISPATCH",
        "payload": {"date": day.isoformat(), "reason": reason, "order_id": str(order.id)},
    }, operation)
    apply_lines(move, [(r.occupation, r.category, r.quality, -r.quantity) for r in rows])
    shipment = SaleDispatch.objects.create(
        order=order, movement=move, actor=actor, preparation=order.preparation,
    )
    for row in rows:
        data = line_snapshot(row.occupation)
        born_from, born_until = row.occupation.lot.born_from, row.occupation.lot.born_until
        data["age_days_min"] = (day - (born_until or born_from)).days if born_from else None
        data["age_days_max"] = (day - born_from).days if born_from else None
        SaleDispatchDetail.objects.create(
            dispatch=shipment, line=row.line, occupation=row.occupation,
            category=row.category, quality=row.quality, quantity=row.quantity, snapshot=data,
        )
    record(actor, "cuy_movement", move.id, "SALE_DISPATCH", after={
        "order_id": order.id, "quantity": sum(row.quantity for row in rows),
    }, reason=reason, operation=operation)
    sale_notice(order, "SALE_DISPATCHED", operation.event_id)
    return shipment


def handle(actor, c, operation):
    kind, p = c["type"], c["payload"]
    if kind == "SALE_CREATE":
        require_admin(actor)
        if SaleOrder.objects.filter(pk=c["entity_id"]).exists():
            fail("UUID de orden ya utilizado.", "IDEMPOTENCY_CONFLICT")
        from apps.catalog.models import Location

        center = get(Location, p["center_id"])
        lock_centers([center.id])
        if center.id not in enabled_centers():
            fail("Seleccione un centro con Cuyes habilitado.", "VALIDATION_ERROR", 422)
        point = get(Location, p["point_id"]) if p.get("point_id") else None
        if (p["mode"] == "PUNTO" and (not point or point.kind != "PUNTO_VENTA" or not point.active)) or (p["mode"] == "DIRECTO" and point):
            fail("La modalidad y el punto de venta no coinciden.", "VALIDATION_ERROR", 422)
        order = SaleOrder.objects.create(
            id=c["entity_id"], code=f"CUY-{c['entity_id'].replace('-', '').upper()}",
            center=center, manager=actor, client_name=p["client_name"],
            client_reference=p["client_reference"], client_contact=p["client_contact"],
            mode=p["mode"], point=point, currency=p["currency"], total=0, reason=p["reason"],
        )
        if len({i["id"] for i in p["items"]}) != len(p["items"]):
            fail("IDs de línea duplicados.", "VALIDATION_ERROR", 422)
        for item in p["items"]:
            if SaleLine.objects.filter(pk=item["id"]).exists():
                fail("UUID de línea ya utilizado.", "IDEMPOTENCY_CONFLICT")
            make_line(order, item).save(force_insert=True)
        order.total = money(sum(line.total for line in order.lines.all()))
        # Creation starts at version 1; revision helper increments subsequent commands.
        order.version = 0
        result = revision(actor, order, kind, p["reason"], operation)
        sale_notice(order, "SALE_REQUESTED", operation.event_id)
        return result

    order = lock_order(c["entity_id"])
    authorize(actor, c)
    expect_version(order, c)
    if kind == "SALE_CONFIRM":
        require_state(order, ["SOLICITADO", "VENCIDO", "RESERVADO"])
        existing = SaleReservation.objects.select_for_update().filter(order=order, state="IMPAGA").first()
        if existing:
            if not expire_locked(actor, order, existing):
                fail("La orden ya está reservada.")
        if order.center_id not in enabled_centers():
            fail("Cuyes no habilitado en el centro.")
        check_demand(order)
        reserve = SaleReservation.objects.create(
            order=order, center=order.center,
            expires_at=timezone.now() + timedelta(minutes=max(1, settings.CUY_SALES_RESERVATION_MINUTES)),
        )
        for (category, quality), quantity in demand(order).items():
            ReservationDetail.objects.create(reservation=reserve, category=category, quality=quality, quantity=quantity)
        order.state, order.shortage = "RESERVADO", False
        sale_notice(order, "SALE_CONFIRMED", operation.event_id)
    elif kind == "SALE_REJECT":
        require_state(order, ["SOLICITADO"])
        order.state = "RECHAZADO"
        sale_notice(order, "SALE_REJECTED", operation.event_id)
    elif kind == "SALE_PROPOSE":
        require_state(order, ["SOLICITADO"])
        ids = {str(line.id) for line in order.lines.all()}
        if len({i["line_id"] for i in p["items"]}) != len(p["items"]) or any(i["line_id"] not in ids for i in p["items"]):
            fail("Las líneas propuestas no pertenecen a la orden.", "VALIDATION_ERROR", 422)
        SaleProposal.objects.create(order=order, author=actor, items=p["items"], reason=p["reason"])
        order.state = "AJUSTE_PENDIENTE"
        sale_notice(order, "SALE_PROPOSED", operation.event_id)
    elif kind == "SALE_PROPOSAL_REVIEW":
        require_state(order, ["AJUSTE_PENDIENTE"])
        proposal = get(SaleProposal, p["proposal_id"])
        if proposal.order_id != order.id or proposal.state != "PENDIENTE":
            fail("Propuesta no vigente.")
        if p["approve"]:
            for item in proposal.items:
                line = order.lines.get(pk=item["line_id"])
                line.units = item["units"]
                line.animal_count = line.units * sum(i["quantity"] for i in line.recipe)
                if "weight_kg" in item:
                    if line.kind != "PESO":
                        fail("Peso propuesto en una línea no facturada por KG.", "VALIDATION_ERROR", 422)
                    line.weight_kg = Decimal(item["weight_kg"])
                line.total = money(line.unit_price * (line.weight_kg if line.kind == "PESO" else line.units))
                line.save()
            order.total = money(sum(line.total for line in order.lines.all()))
        proposal.state, proposal.reviewed_by = "ACEPTADA" if p["approve"] else "RECHAZADA", actor
        proposal.save()
        order.state = "SOLICITADO"
        sale_notice(order, "SALE_REQUESTED", operation.event_id)
    elif kind == "SALE_PAY":
        require_state(order, ["RESERVADO"])
        reserve = reservation(order, live=True)
        validate_stock(order)
        if money(p["amount"]) != order.total or p["currency"] != order.currency:
            fail("El pago debe corresponder al importe y moneda aceptados.", "PAYMENT_AMOUNT_MISMATCH")
        evidence = get(PaymentEvidence, p["evidence_id"])
        if SalePayment.objects.filter(evidence=evidence).exists():
            fail("Este comprobante ya valida otro pago.")
        SalePayment.objects.create(
            order=order, amount=p["amount"], currency=p["currency"], method=p["method"],
            reference=p["reference"], evidence=evidence, validated_by=actor, operation=operation,
        )
        reserve.state = "PAGADA"
        reserve.save(update_fields=["state"])
        order.state, order.approved_total = "PAGADO", order.total
        sale_notice(order, "SALE_PAID", operation.event_id)
    elif kind == "SALE_DRIVER":
        require_state(order, PAID)
        if order.mode != "PUNTO":
            fail("Una orden de recojo directo no tiene conductor.")
        driver = get(User, p["driver_id"])
        require_role(driver, "TRANSPORTE", order.center_id)
        order.driver = driver
        invalidate(order)
        sale_notice(order, "SALE_DRIVER", operation.event_id)
    elif kind == "SALE_SELECT":
        require_state(order, PAID)
        reservation(order, live=True)
        if len(set(p["shed_ids"])) != len(p["shed_ids"]):
            fail("Galpones duplicados.", "VALIDATION_ERROR", 422)
        for shed_id in p["shed_ids"]:
            shed = get(Shed, shed_id)
            require_shed(actor, shed)
            if shed.center_id != order.center_id:
                fail("Los orígenes deben pertenecer al centro de la orden.", "VALIDATION_ERROR", 422)
        previous = list(order.preparation.selections.all()) if order.preparation_id else []
        prep = SalePreparation.objects.create(order=order, author=actor)
        for row in previous:
            if str(row.occupation.pen.shed_id) not in p["shed_ids"]:
                DispatchSelection.objects.create(
                    preparation=prep, line=row.line, occupation=row.occupation,
                    category=row.category, quality=row.quality, quantity=row.quantity,
                )
        keys = set()
        for item in p["items"]:
            occ = occupation(item["occupation_id"])
            require_pen(actor, occ.pen, write=True)
            line = get(SaleLine, item["line_id"])
            if line.order_id != order.id or str(occ.pen.shed_id) not in p["shed_ids"]:
                fail("Línea o galpón de origen no autorizado.", "PERMISSION_DENIED", 403)
            key = (line.id, occ.id, item["category"], item["quality"])
            if key in keys:
                fail("Selección duplicada.", "VALIDATION_ERROR", 422)
            keys.add(key)
            DispatchSelection.objects.create(
                preparation=prep, line=line, occupation=occ,
                category=item["category"], quality=item["quality"], quantity=item["quantity"],
            )
        order.preparation, order.state = prep, "EN_PREPARACION"
        invalidate(order)
        validate_plan(order, complete=False)
    elif kind in ["SALE_ORIGIN", "SALE_PICKUP"]:
        require_state(order, PAID)
        validate_stock(order)
        rows = validate_plan(order)
        if p["preparation_id"] != str(order.preparation_id) or p["round"] != order.confirmation_round:
            fail("Cambió el detalle: confirme la preparación vigente.", "PREPARATION_CHANGED")
        if kind == "SALE_PICKUP":
            if p["shed_ids"]:
                fail("El conductor no confirma galpones.", "VALIDATION_ERROR", 422)
            if SaleConformity.objects.filter(preparation=order.preparation, round=order.confirmation_round, stage="CONDUCTOR").exists():
                fail("La conformidad ya está registrada.")
            SaleConformity.objects.create(preparation=order.preparation, round=order.confirmation_round, stage="CONDUCTOR", actor=actor)
        else:
            selected_sheds = {str(row.occupation.pen.shed_id) for row in rows}
            if not p["shed_ids"] or len(set(p["shed_ids"])) != len(p["shed_ids"]):
                fail("Seleccione sus galpones de origen.", "VALIDATION_ERROR", 422)
            for shed_id in p["shed_ids"]:
                if shed_id not in selected_sheds:
                    fail("El galpón no participa en la preparación.", "VALIDATION_ERROR", 422)
                require_shed(actor, get(Shed, shed_id))
                if SaleConformity.objects.filter(preparation=order.preparation, round=order.confirmation_round, shed_id=shed_id, stage="GALPONERO").exists():
                    fail("Este galpón ya dio conformidad.")
                SaleConformity.objects.create(preparation=order.preparation, round=order.confirmation_round, stage="GALPONERO", shed_id=shed_id, actor=actor)
    elif kind == "SALE_DEPART":
        if order.mode != "PUNTO":
            fail("Recojo directo requiere PIN.")
        physical_dispatch(actor, order, operation, p["reason"])
        SaleDelivery.objects.create(order=order, stage="RECOGIDA_ORIGEN", registered_by=actor,
                                    physical_responsible=order.driver.name, reference="Conformidades de origen y conductor")
    elif kind == "SALE_ARRIVE":
        require_state(order, ["EN_RUTA"])
        SaleDelivery.objects.create(order=order, stage="LLEGADA_PUNTO", registered_by=actor,
                                    physical_responsible=p["physical_responsible"], reference=p["reference"])
        order.state = "EN_PUNTO"
        if p["delivered_to_client"]:
            SaleDelivery.objects.create(order=order, stage="ENTREGA_CLIENTE", registered_by=actor,
                                        physical_responsible=p["physical_responsible"], reference=p["reference"])
            order.state = "ENTREGADO"
        sale_notice(order, "SALE_DELIVERED", operation.event_id)
    elif kind == "SALE_COLLECT":
        require_state(order, ["EN_PUNTO"])
        SaleDelivery.objects.create(order=order, stage="ENTREGA_CLIENTE", registered_by=actor,
                                    physical_responsible=p["physical_responsible"], reference=p["reference"])
        order.state = "ENTREGADO"
        sale_notice(order, "SALE_DELIVERED", operation.event_id)
    elif kind == "SALE_CANCEL":
        if order.state in DISPATCHED + ["CANCELADO", "RECHAZADO"]:
            fail("La orden no admite cancelación. No se implementan devoluciones físicas.")
        paid = SalePayment.objects.filter(order=order).exists()
        if paid and not p.get("payment_treatment", "").strip():
            fail("Debe resolver explícitamente el tratamiento del pago validado.", "PAYMENT_RESOLUTION_REQUIRED")
        reserves = SaleReservation.objects.filter(order=order, state__in=["IMPAGA", "PAGADA"])
        for reserve in reserves:
            release(reserve, "LIBERADA")
        order.state = "CANCELADO"
        if paid:
            SaleFinancialReview.objects.create(
                order=order, previous_total=order.total, new_total=order.total, difference=0,
                treatment="CANCELACION", reference=p["payment_treatment"], reason=p["reason"], actor=actor,
            )
        sale_notice(order, "SALE_CANCELLED", operation.event_id)
    elif kind == "SALE_WEIGH":
        require_state(order, ["SOLICITADO", "RESERVADO", *PAID])
        line = get(SaleLine, p["line_id"])
        if line.order_id != order.id or line.kind != "PESO":
            fail("La línea no es una venta por peso de esta orden.", "VALIDATION_ERROR", 422)
        line.weight_kg, line.total = Decimal(p["weight_kg"]), money(Decimal(p["weight_kg"]) * line.unit_price)
        line.save()
        order.total = money(sum(line.total for line in order.lines.all()))
        if SalePayment.objects.filter(order=order).exists():
            order.financial_hold = True
            invalidate(order)
    elif kind == "SALE_FINANCE":
        require_state(order, PAID)
        if not order.financial_hold:
            fail("No hay diferencia económica pendiente.")
        difference = money(order.total - order.approved_total)
        treatment = p["treatment"]
        if (difference > 0 and treatment == "DEVOLUCION") or (difference < 0 and treatment == "COBRO_ADICIONAL"):
            fail("El tratamiento no corresponde al signo de la diferencia.", "VALIDATION_ERROR", 422)
        evidence = get(PaymentEvidence, p["evidence_id"]) if p.get("evidence_id") else None
        if treatment != "ABSORBIDO" and difference != 0 and not evidence:
            fail("Adjunte comprobante de la diferencia verificada.", "VALIDATION_ERROR", 422)
        SaleFinancialReview.objects.create(
            order=order, previous_total=order.approved_total, new_total=order.total,
            difference=difference, treatment=treatment, reference=p["reference"],
            evidence=evidence, reason=p["reason"], actor=actor,
        )
        order.financial_hold, order.approved_total = False, order.total
    elif kind == "SALE_RESOLVE_STOCK":
        require_state(order, ["RESERVADO", *PAID])
        if bool(shortage_keys(order.center_id) & set(demand(order))) or selection_missing(order):
            fail("El faltante persiste. Reponga físicamente, revise la selección o resuelva la orden pagada.", "SALE_STOCK_SHORTAGE")
        order.shortage = False
        invalidate(order)
    return revision(actor, order, kind, p["reason"], operation)


def commands():
    return {kind: (serializer, handle, authorize) for kind, serializer in SALE_COMMANDS.items()}


@transaction.atomic
def save_module(actor, data):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    require_admin(actor)
    module = BreedingModule.objects.select_for_update().filter(pk=data["id"]).first()
    before = list(module.components.values("category", "quality", "quantity")) if module else []
    keys = [(item["category"], item["quality"]) for item in data["components"]]
    if len(keys) != len(set(keys)) or not {"MACHO", "HEMBRA"}.issubset({c for c, q in keys}):
        fail("Un módulo reproductivo requiere ambos sexos y componentes no duplicados.", "VALIDATION_ERROR", 422)
    module = module or BreedingModule(id=data["id"])
    module.name, module.active = data["name"], data["active"]
    module.save()
    module.components.all().delete()
    for component in data["components"]:
        ModuleComponent.objects.create(module=module, **component)
    record(actor, "cuy_module", module.id, "SAVE_MODULE", before={"components": before},
           after={"name": module.name, "active": module.active, "components": data["components"]}, reason=data["reason"])
    return module
