from collections import defaultdict
from types import SimpleNamespace

from django.utils import timezone

from apps.accounts.access import active_assignments, is_admin, require_admin

from .access import enabled_centers, pens_for, sheds_for
from .models import (
    Balance,
    BreedingModule,
    SaleOrder,
)
from .sales_services import (
    line_snapshot_data,
    require_handoffs,
    require_worker,
    validate_plan,
    validate_stock,
)
from .sales_stock import available, claimed_buckets, demand, selection_missing, shortage_keys
from .services import fail


def workspace(actor, requested=None):
    value = requested or ("ADMIN" if is_admin(actor) else "GALPONERO" if active_assignments(actor).filter(role_id="GALPONERO").exists() else "TRANSPORTE")
    if value == "ADMIN":
        require_admin(actor)
    elif not active_assignments(actor).filter(role_id=value).exists():
        fail("No tiene este espacio de trabajo.", "PERMISSION_DENIED", 403)
    return value


def orders_for(actor, role):
    query = SaleOrder.objects.select_related("center", "point", "driver", "manager", "preparation")
    if role == "ADMIN":
        require_admin(actor)
        return query
    if role == "GALPONERO":
        return query.filter(center_id__in=sheds_for(actor).values("center_id"))
    return query.filter(
        mode="PUNTO", driver=actor, center_id__in=active_assignments(actor).filter(role_id="TRANSPORTE").values("location_id"),
        state__in=["PAGADO", "EN_PREPARACION", "EN_RUTA", "EN_PUNTO", "ENTREGADO"],
    )


def module_data(module):
    return {"id": module.id, "name": module.name, "active": module.active,
            "components": list(module.components.order_by("category", "quality").values("category", "quality", "quantity"))}


def availability_data(actor, center_id, role):
    if role == "TRANSPORTE":
        fail("Transporte no consulta inventario comercial.", "PERMISSION_DENIED", 403)
    if center_id not in enabled_centers():
        fail("Centro no habilitado.", "NOT_FOUND", 404)
    if role != "ADMIN":
        require_worker(actor, SimpleNamespace(center_id=center_id))
    balances = available(center_id, pens=None if role == "ADMIN" else pens_for(actor))
    modules = []
    for module in BreedingModule.objects.filter(active=True).order_by("name", "id"):
        components = list(module.components.all())
        kits = min((balances.get((c.category, c.quality), 0) // c.quantity for c in components), default=0)
        modules.append({**module_data(module), "offerable": kits})
    return {
        "center_id": str(center_id), "referential": True,
        "scope": "CENTRO" if role == "ADMIN" else "MIS_GALPONES",
        "buckets": [{"category": c, "quality": q, "available": n} for (c, q), n in sorted(balances.items())],
        "modules": modules,
    }


def candidates(actor, order):
    require_worker(actor, order)
    buckets = claimed_buckets(exclude_order=order.id)
    needed = demand(order)
    result = []
    query = Balance.objects.filter(
        quantity__gt=0, occupation__pen__in=pens_for(actor),
        occupation__pen__shed__center_id=order.center_id, occupation__pen__active=True,
        occupation__pen__shed__active=True,
    ).select_related("occupation__lot", "occupation__pen__shed").order_by(
        "occupation__lot__opened_on", "occupation__lot_id", "occupation_id", "category", "quality",
    )
    for b in query:
        if (b.category, b.quality) not in needed:
            continue
        n = max(0, b.quantity - buckets.get((str(b.occupation_id), b.category, b.quality), 0))
        if n:
            result.append({
                "occupation_id": b.occupation_id, "lot_id": b.occupation.lot_id,
                "pen_id": b.occupation.pen_id, "pen": b.occupation.pen.code,
                "shed_id": b.occupation.pen.shed_id, "category": b.category, "quality": b.quality,
                "available": n, "opened_on": b.occupation.lot.opened_on,
            })
    return result


def order_data(actor, order, role):
    own_pens = set(pens_for(actor).values_list("id", flat=True)) if role == "GALPONERO" else None
    reserves = order.reservations.order_by("-created_at")
    reserve = reserves.first()
    expired = bool(reserve and reserve.state == "IMPAGA" and reserve.expires_at <= timezone.now())
    ready = False
    if order.state in ["PAGADO", "EN_PREPARACION"] and not order.financial_hold and order.approved_total == order.total:
        from apps.common.errors import DomainError

        try:
            rows = validate_plan(order)
            validate_stock(order)
            require_handoffs(order, rows, driver=order.mode == "PUNTO")
            ready = order.mode == "PUNTO" or bool(order.pin_hash)
        except DomainError:
            pass
    current_shortage = order.shortage or bool(shortage_keys(order.center_id) & set(demand(order))) or selection_missing(order) if order.state in ["RESERVADO", "PAGADO", "EN_PREPARACION"] else False
    prep = None
    if order.preparation_id:
        rows = order.preparation.selections.select_related("occupation__pen")
        prep = {
            "id": order.preparation_id, "round": order.confirmation_round,
            "items": [
                {"line_id": r.line_id, "occupation_id": r.occupation_id,
                 "pen": r.occupation.pen.code, "shed_id": r.occupation.pen.shed_id,
                 "category": r.category, "quality": r.quality, "quantity": r.quantity}
                for r in rows if own_pens is None or r.occupation.pen_id in own_pens
            ],
            "other_allocations": [
                {"line_id": str(line_id), "category": category, "quality": quality, "quantity": n}
                for (line_id, category, quality), n in _other_allocations(rows, own_pens).items()
            ],
            "conformities": list(order.preparation.conformities.filter(round=order.confirmation_round).values(
                "stage", "shed_id", "actor_id", "registered_at",
            )),
        }
    shipment = None
    if hasattr(order, "dispatch"):
        shipment = {
            "id": order.dispatch.id, "movement_id": order.dispatch.movement_id,
            "departed_at": order.dispatch.departed_at,
            "details": [
                {"line_id": d.line_id, "category": d.category, "quality": d.quality,
                 "quantity": d.quantity, "snapshot": d.snapshot}
                for d in order.dispatch.details.all()
                if own_pens is None or d.occupation.pen_id in own_pens
            ],
        }
    lines = []
    for line in order.lines.order_by("id"):
        data = line_snapshot_data(line)
        if role != "ADMIN":
            for key in ["unit_price", "total"]:
                data.pop(key, None)
        lines.append(data)
    actions = []
    if role == "ADMIN":
        if order.state == "AJUSTE_PENDIENTE":
            actions.append("SALE_PROPOSAL_REVIEW")
        if order.state == "RESERVADO" and not expired:
            actions.append("SALE_PAY")
        if order.state in ["PAGADO", "EN_PREPARACION"]:
            actions += ["SALE_FINANCE"] if order.financial_hold else []
            actions += ["SALE_RESOLVE_STOCK"] if current_shortage else []
            actions += ["PIN_GENERATE"] if order.mode == "DIRECTO" and not order.financial_hold else ["SALE_DRIVER"] if order.mode == "PUNTO" else []
        if order.state in ["SOLICITADO", "RESERVADO", "PAGADO", "EN_PREPARACION"] and any(line.kind == "PESO" for line in order.lines.all()):
            actions.append("SALE_WEIGH")
        if order.state == "EN_PUNTO":
            actions.append("SALE_COLLECT")
        if order.state not in ["EN_RUTA", "EN_PUNTO", "ENTREGADO", "CANCELADO", "RECHAZADO"]:
            actions.append("SALE_CANCEL")
    elif role == "GALPONERO":
        if order.state in ["SOLICITADO", "VENCIDO"] or expired:
            actions += ["SALE_CONFIRM"]
        if order.state == "SOLICITADO":
            actions += ["SALE_REJECT", "SALE_PROPOSE"]
        if order.state in ["PAGADO", "EN_PREPARACION"]:
            actions += ["SALE_SELECT", "SALE_ORIGIN"]
            if ready:
                actions += ["PIN_DELIVER"] if order.mode == "DIRECTO" else ["SALE_DEPART"]
    elif role == "TRANSPORTE":
        if order.state in ["PAGADO", "EN_PREPARACION"] and order.preparation_id:
            actions += ["SALE_PICKUP"]
        if order.state == "EN_RUTA":
            actions += ["SALE_ARRIVE"]
    stage = 4 if order.state == "ENTREGADO" else 3 if order.state in ["EN_PREPARACION", "EN_RUTA", "EN_PUNTO"] else 2 if order.state in ["PAGADO", "RESERVADO"] else 1
    data = {
        "id": order.id, "code": order.code, "center_id": order.center_id, "center": order.center.name,
        "mode": order.mode, "point": {"id": order.point_id, "name": order.point.name} if order.point_id else None,
        "driver": {"id": order.driver_id, "name": order.driver.name} if order.driver_id else None,
        "state": order.state, "display_state": "RESERVA_VENCIDA" if expired else "LISTO_PARA_DESPACHAR" if ready else order.state,
        "ready_to_dispatch": ready,
        "stage": stage, "version": order.version, "shortage": current_shortage,
        "financial_hold": order.financial_hold, "client": {"name": order.client_name},
        "lines": lines, "preparation": prep, "dispatch": shipment, "actions": actions,
        "reservation": {
            "id": reserve.id, "state": "VENCIDA" if expired else reserve.state, "expires_at": reserve.expires_at,
            "created_at": reserve.created_at, "released_at": reserve.released_at, "consumed_at": reserve.consumed_at,
            "details": list(reserve.details.values("category", "quality", "quantity")),
        } if reserve else None,
        "deliveries": list(order.deliveries.order_by("registered_at").values("stage", "physical_responsible", "registered_by_id", "reference", "registered_at")),
        "updated_at": order.updated_at,
    }
    if role in ["ADMIN", "TRANSPORTE"]:
        data["client"]["contact"] = order.client_contact
    if role != "TRANSPORTE":
        data["reason"] = order.reason
    if role == "ADMIN":
        data["manager"] = {"id": order.manager_id, "name": order.manager.name}
        data.update(total=str(order.total), currency=order.currency,
                    approved_total=str(order.approved_total) if order.approved_total is not None else None)
        data["client"]["reference"] = order.client_reference
        data["pin_status"] = {
            "generated": bool(order.pin_hash), "consumed_at": order.pin_consumed_at,
            "failures": order.pin_failures, "generation": order.pin_generation,
        }
        data["payment"] = {
            "amount": str(order.payment.amount), "currency": order.payment.currency,
            "method": order.payment.method, "reference": order.payment.reference,
            "evidence_id": order.payment.evidence_id, "validated_by_id": order.payment.validated_by_id,
            "validated_at": order.payment.validated_at,
        } if hasattr(order, "payment") else None
        data["financial_reviews"] = list(order.financial_reviews.order_by("registered_at").values())
        for review in data["financial_reviews"]:
            for field in ["previous_total", "new_total", "difference"]:
                review[field] = str(review[field])
        data["reservation_history"] = [
            {"id": r.id, "state": r.state, "created_at": r.created_at,
             "expires_at": r.expires_at, "released_at": r.released_at, "consumed_at": r.consumed_at,
             "details": list(r.details.values("category", "quality", "quantity"))}
            for r in reserves
        ]
        data["proposals"] = list(order.proposals.order_by("created_at").values())
        data["revisions"] = list(order.revisions.order_by("registered_at").values("action", "reason", "snapshot", "registered_at"))
    return data


def _other_allocations(rows, own_pens):
    result = defaultdict(int)
    if own_pens is not None:
        for row in rows:
            if row.occupation.pen_id not in own_pens:
                result[(row.line_id, row.category, row.quality)] += row.quantity
    return result
