from collections import defaultdict
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.access import is_admin, require_admin
from apps.audit.services import record, snapshot
from apps.common.errors import DomainError
from apps.notifications.services import notify

from .access import destination_pens, enabled_centers, require_pen, require_shed
from .models import (
    Alert,
    Balance,
    CountDetail,
    CuyLot,
    DailyReport,
    DailyRevision,
    LedgerLine,
    Movement,
    Occupation,
    Pen,
    PhysicalCount,
    Shed,
    Transfer,
)
from .serializers import COMMANDS


def fail(message, code="INVALID_STATE", status=409):
    raise DomainError(code, message, status)


def get(model, pk):
    query = model.objects if hasattr(model, "objects") else model
    obj = query.filter(pk=pk).first()
    if obj is None:
        fail("Registro no disponible.", "NOT_FOUND", 404)
    return obj


def op_date(value):
    day = value if isinstance(value, date) else date.fromisoformat(value)
    if day > timezone.localdate():
        fail("La fecha operativa no puede ser futura.", "VALIDATION_ERROR", 422)
    return day


def occupation(pk):
    if not pk:
        fail("Seleccione una ocupación.", "VALIDATION_ERROR", 422)
    return get(Occupation.objects.select_related("pen__shed__center", "lot"), pk)


def actor_pens(kind, p):
    if kind in ["CUY_BIRTH", "CUY_WEAN"]:
        return [occupation(p["occupation_id"]).pen]
    if kind in ["CUY_OPEN", "CUY_COUNT"]:
        return [get(Pen, p["pen_id"])]
    if kind in ["CUY_MOVE", "CUY_DISPATCH"]:
        return [get(Pen, p["source_id"])]
    if kind == "CUY_RECEIVE":
        return [get(Transfer, p["transfer_id"]).destination]
    if kind in ["CUY_DEATH", "CUY_RECLASS"]:
        return [occupation(item.get("occupation_id")).pen for item in p["items"]]
    return []


def authorize(actor, command):
    kind, p = command["type"], command["payload"]
    if kind in ["CUY_REVIEW", "CUY_REOPEN", "CUY_RESOLVE", "CUY_ALERTS", "CUY_COMPENSATE"]:
        require_admin(actor)
    elif kind == "CUY_REDIRECT":
        transfer = get(Transfer, p["transfer_id"])
        if not is_admin(actor):
            # Receiving endpoint can redirect to another pen of its own center.
            require_pen(actor, transfer.destination)
            dest = get(Pen, p["destination_id"])
            require_pen(actor, dest, write=True)
            if dest.shed.center_id != transfer.destination.shed.center_id:
                fail("Redirección a otro centro requiere ADMIN.", "PERMISSION_DENIED", 403)
    elif kind == "CUY_CLOSE":
        require_shed(actor, get(Shed, p["shed_id"]))
    else:
        for pen in actor_pens(kind, p):
            require_pen(actor, pen, write=True)
    if kind == "CUY_RECLASS" and p["new_quality"] == "C":
        require_admin(actor)


def recipients():
    from django.db.models import Q

    from apps.accounts.models import RoleAssignment

    return RoleAssignment.objects.filter(
        role_id="ADMIN", scope="GLOBAL", starts_at__lte=timezone.now(), user__is_active=True,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=timezone.now())).values_list("user_id", flat=True)


def alert(pen, key, kind, text):
    obj, created = Alert.objects.get_or_create(
        key=key, defaults={"pen": pen, "kind": kind, "text": text},
    )
    if created:
        notify(recipients=recipients(), type="CUY_ALERT", source_event_id=obj.id,
               entity_type="cuy_pen", entity_id=pen.id, title="Cuyes: requiere revisión", text=text)
    return obj


def compatible(pen, category):
    allowed = {
        "MATERNIDAD": {"MACHO", "HEMBRA", "LACTANTE"},
        "RECRIA_MACHOS": {"MACHO"}, "RECRIA_HEMBRAS": {"HEMBRA"},
        "ACABADO": {"MACHO", "HEMBRA"}, "ENFERMERIA": {"MACHO", "HEMBRA", "LACTANTE"},
    }
    if category not in allowed[pen.purpose]:
        fail(f"{category} no es compatible con {pen.code}.", "INCOMPATIBLE_PURPOSE", 422)


def total(pen):
    return Balance.objects.filter(occupation__pen=pen).aggregate(n=Sum("quantity"))["n"] or 0


def lock_scope(pen_ids, day, *, check_closed=True, extra_sheds=()):
    # Every writer (including config/count/close) takes sheds then pens, in UUID order.
    # This serializes capacity across different occupations and closes across all pens.
    shed_ids = set(Pen.objects.filter(id__in=pen_ids).values_list("shed_id", flat=True)) | set(extra_sheds)
    from .locking import lock_centers

    lock_centers(Shed.objects.filter(id__in=shed_ids).values_list("center_id", flat=True))
    list(Shed.objects.select_for_update().filter(id__in=shed_ids).order_by("id"))
    pens = {str(p.id): p for p in Pen.objects.select_for_update().filter(id__in=pen_ids).order_by("id").select_related("shed__center")}
    if check_closed and DailyReport.objects.filter(shed_id__in=shed_ids, date=day, state="CERRADO").exists():
        fail("El día está cerrado. ADMIN debe reabrirlo con motivo.", "DAY_CLOSED")
    return pens


def new_occupation(lot, pen, day):
    obj = Occupation.objects.filter(lot=lot, pen=pen, closed_on__isnull=True).first()
    return obj or Occupation.objects.create(lot=lot, pen=pen, started_on=day)


def line_snapshot(occ):
    return snapshot({
        "center_id": occ.pen.shed.center_id, "center": occ.pen.shed.center.name,
        "pen_id": occ.pen_id,
        "shed_id": occ.pen.shed_id, "shed": occ.pen.shed.code, "pen": occ.pen.code,
        "lot_id": occ.lot_id, "provenance": occ.lot.provenance,
        "parent_id": occ.lot.parent_id, "source_occupation_id": occ.lot.source_occupation_id,
        "opened_on": occ.lot.opened_on, "born_from": occ.lot.born_from,
        "born_until": occ.lot.born_until, "installed_on": occ.lot.installed_on,
    })


def apply_lines(movement, changes, *, controlled=True):
    buckets = defaultdict(int)
    objects = {}
    for occ, category, quality, delta in changes:
        key = (occ.id, category, quality)
        buckets[key] += delta
        objects[occ.id] = occ
    pen_deltas = defaultdict(int)
    for (occ_id, category, quality), delta in sorted(buckets.items(), key=lambda x: str(x[0])):
        if not delta:
            continue
        occ = objects[occ_id]
        if movement.date < occ.started_on:
            fail("La novedad precede a la ocupación.", "INVALID_DATE", 422)
        if movement.kind not in ["OPEN", "REVIEW"] and PhysicalCount.objects.filter(
            pen=occ.pen, opening=False, date__gt=movement.date,
            registered_at__lt=movement.registered_at,
        ).exists():
            fail("Existe un conteo al corte. Registre el hecho después del corte o solicite revisión administrativa.", "COUNT_CUT_LOCKED")
        if delta > 0:
            if occ.closed_on and Occupation.objects.filter(
                lot=occ.lot, pen=occ.pen, closed_on__isnull=True,
            ).exclude(pk=occ.pk).exists():
                fail("El lote tiene otra ocupación abierta; revise la conciliación sin alterar el historial.", "OCCUPATION_REVIEW_REQUIRED")
            if not occ.pen.active or not occ.pen.shed.active or occ.pen.shed.center_id not in enabled_centers():
                fail("El destino dejó de estar disponible.")
            compatible(occ.pen, category)
        bucket, _ = Balance.objects.get_or_create(occupation=occ, category=category, quality=quality)
        if bucket.quantity + delta < 0:
            fail("Saldo insuficiente; conserve la intención para revisión.", "INSUFFICIENT_BALANCE")
        # A late decrement must also be consistent with every subsequent operational cut.
        running = LedgerLine.objects.filter(
            occupation=occ, category=category, quality=quality,
            movement__date__lte=movement.date,
        ).aggregate(n=Sum("delta"))["n"] or 0
        if running + delta < 0:
            fail("La cantidad no existía en la fecha declarada.", "HISTORICAL_CONFLICT")
        future = LedgerLine.objects.filter(
            occupation=occ, category=category, quality=quality, movement__date__gt=movement.date,
        ).values("movement__date").annotate(n=Sum("delta")).order_by("movement__date")
        for row in future:
            running += row["n"]
            if running + delta < 0:
                fail("El cambio dejaría un corte histórico negativo.", "HISTORICAL_CONFLICT")
        bucket.quantity += delta
        bucket.save(update_fields=["quantity"])
        LedgerLine.objects.create(
            movement=movement, occupation=occ, category=category, quality=quality,
            delta=delta, snapshot=line_snapshot(occ),
        )
        pen_deltas[occ.pen_id] += delta
    for pen_id, delta in pen_deltas.items():
        pen = next(o.pen for o in objects.values() if o.pen_id == pen_id)
        population = total(pen)
        if controlled and delta > 0 and population > pen.capacity:
            fail(f"Se excedería la capacidad de {pen.code}.", "CAPACITY_EXCEEDED")
        if population > pen.capacity:
            alert(pen, f"capacity:{pen.id}", "CAPACITY", f"{pen.code}: {population} animales / capacidad {pen.capacity}.")
    for occ in objects.values():
        remaining = Balance.objects.filter(occupation=occ).aggregate(n=Sum("quantity"))["n"] or 0
        occ.closed_on = None if remaining else movement.date
        occ.save(update_fields=["closed_on"])
    from .sales_stock import detect_shortages

    detect_shortages({occ.pen.shed.center_id for occ in objects.values()}, movement.id, movement.actor)


def movement_for(actor, c, operation, *, compensates=None):
    if Movement.objects.filter(pk=c["entity_id"]).exists():
        fail("Identificador de movimiento ya utilizado.", "IDEMPOTENCY_CONFLICT")
    metadata = dict(c["payload"])
    for field in ["source_id", "destination_id", "pen_id"]:
        if metadata.get(field):
            pen = get(Pen.objects.select_related("shed__center"), metadata[field])
            metadata[f"{field}_snapshot"] = {
                "pen": pen.code, "shed": pen.shed.code, "center": pen.shed.center.name,
            }
    return Movement.objects.create(
        id=c["entity_id"], operation=operation, actor=actor, date=op_date(c["payload"]["date"]),
        kind=c["type"].removeprefix("CUY_"), reason=c["payload"]["reason"],
        metadata=metadata, compensates=compensates,
    )


def validate_items(items, *, positive=True):
    if positive and any(i["quantity"] <= 0 for i in items):
        fail("Las cantidades deben ser positivas.", "VALIDATION_ERROR", 422)
    keys = [(i.get("occupation_id"), i.get("pen_id"), i["category"], i["quality"]) for i in items]
    if len(keys) != len(set(keys)):
        fail("Hay líneas duplicadas.", "VALIDATION_ERROR", 422)


def outgoing(p, source):
    validate_items(p["items"])
    changes = []
    for item in p["items"]:
        occ = occupation(item.get("occupation_id"))
        if occ.pen_id != source.id:
            fail("Todas las salidas deben pertenecer a la poza de origen.", "VALIDATION_ERROR", 422)
        changes.append((occ, item["category"], item["quality"], -item["quantity"]))
    return changes


def validate_destination(actor, pen, *, immediate=False):
    if immediate:
        require_pen(actor, pen, write=True)
    elif not is_admin(actor) and not destination_pens(actor).filter(pk=pen.pk).exists():
        fail("Destino sin receptor GALPONERO vigente.", "PERMISSION_DENIED", 403)
    if not pen.active or not pen.shed.active or pen.shed.center_id not in enabled_centers():
        fail("Destino no disponible.")


def handle(actor, c, operation):
    kind, p = c["type"], c["payload"]
    day = op_date(p["date"])
    if kind in ["CUY_RECEIVE", "CUY_REDIRECT"]:
        # Serialize redirection with reception before deciding which shed to lock.
        get(Transfer.objects.select_for_update(), p["transfer_id"])
    # Authorization is repeated under the domain locks below.
    if kind in ["CUY_CLOSE", "CUY_REOPEN"]:
        return daily(actor, c, day)
    if kind == "CUY_RESOLVE":
        require_admin(actor)
        obj = get(Alert.objects.select_for_update(), p["alert_id"])
        if obj.resolved_at:
            fail("La alerta ya está resuelta.")
        obj.resolved_at, obj.resolved_by, obj.reason = timezone.now(), actor, p["reason"]
        obj.save()
        record(actor, "cuy_alert", obj.id, kind, reason=p["reason"])
        return {"alert_id": str(obj.id)}
    if kind == "CUY_ALERTS":
        from .reports import refresh_alerts

        require_admin(actor)
        refresh_alerts(day)
        return {"refreshed": True}
    if kind == "CUY_REVIEW":
        return review(actor, c, operation, day)
    if kind == "CUY_REDIRECT":
        transfer = get(Transfer, p["transfer_id"])
        ids = [transfer.source_id, transfer.destination_id, p["destination_id"]]
        lock_scope(ids, day, check_closed=False)
        transfer = Transfer.objects.select_for_update().get(pk=transfer.id)
        authorize(actor, c)
        if transfer.state != "EN_TRANSITO":
            fail("El traslado ya fue recibido.")
        dest = get(Pen, p["destination_id"])
        validate_destination(actor, dest, immediate=not is_admin(actor))
        check_arrival(dest, transfer.items)
        before = {"destination_id": transfer.destination_id}
        transfer.destination = dest
        transfer.save(update_fields=["destination"])
        record(actor, "cuy_transfer", transfer.id, kind, before=before,
               after={"destination_id": dest.id}, reason=p["reason"], operation=operation)
        return {"transfer_id": str(transfer.id)}
    if kind == "CUY_COMPENSATE":
        original = get(Movement, p["movement_id"])
        original = Movement.objects.select_for_update().get(pk=original.pk)
        if original.kind not in ["BIRTH", "DEATH", "WEAN", "MOVE", "RECLASS"]:
            fail("Esta operación exige su flujo específico de revisión.")
        if Movement.objects.filter(compensates=original).exists():
            fail("El movimiento ya tiene compensación.")
        original_lines = list(original.lines.select_related("occupation__lot", "occupation__pen__shed__center"))
        lock_scope([line.occupation.pen_id for line in original_lines], day)
        require_admin(actor)
        move = movement_for(actor, c, operation, compensates=original)
        apply_lines(move, [(line.occupation, line.category, line.quality, -line.delta) for line in original_lines])
        return {"movement_id": str(move.id)}

    pen_ids = [pen.id for pen in actor_pens(kind, p)]
    if kind == "CUY_WEAN":
        pen_ids += [i.get("pen_id") for i in p["destinations"]]
    if kind in ["CUY_MOVE", "CUY_DISPATCH"]:
        pen_ids += [p["destination_id"]]
    if kind == "CUY_RECEIVE":
        transfer = get(Transfer, p["transfer_id"])
        # No origin-day check at reception; only destination's operational day is affected.
        pen_ids = [transfer.destination_id]
    pens = lock_scope(pen_ids, day)
    authorize(actor, c)
    if Movement.objects.filter(pk=c["entity_id"]).exists():
        fail("Identificador de movimiento ya utilizado.", "IDEMPOTENCY_CONFLICT")
    move = movement_for(actor, c, operation)
    changes = []
    if kind == "CUY_OPEN":
        pen = pens[str(p["pen_id"])]
        if Occupation.objects.filter(pen=pen).exists():
            fail("La poza ya tuvo apertura. Utilice conteo y conciliación.")
        count = PhysicalCount.objects.create(
            id=move.id, pen=pen, date=day, author=actor, opening=True, state="APLICADO",
            reason=p["reason"],
        )
        groups = p.get("groups") or [{"lot": p["lot"], "items": p["items"]}]
        for group in groups:
            validate_items(group["items"], positive=False)
            lot_data = dict(group["lot"])
            for field in ["born_from", "born_until", "installed_on"]:
                if lot_data.get(field):
                    lot_data[field] = date.fromisoformat(lot_data[field])
            start, end = lot_data.get("born_from"), lot_data.get("born_until")
            if (end and not start) or (start and end and end < start) or (start and start > day) or (end and end > day):
                fail("Intervalo de nacimiento no válido.", "VALIDATION_ERROR", 422)
            if lot_data.get("installed_on") and lot_data["installed_on"] > day:
                fail("Instalación posterior a la apertura.", "VALIDATION_ERROR", 422)
            lot = CuyLot.objects.create(opened_on=day, **lot_data)
            occ = new_occupation(lot, pen, day)
            for item in group["items"]:
                if item.get("occupation_id") or item.get("pen_id"):
                    fail("La apertura crea la ocupación.", "VALIDATION_ERROR", 422)
                CountDetail.objects.create(count=count, occupation=occ, category=item["category"],
                                          quality=item["quality"], expected=0, observed=item["quantity"])
                changes.append((occ, item["category"], item["quality"], item["quantity"]))
    elif kind == "CUY_BIRTH":
        occ = occupation(p["occupation_id"])
        if occ.closed_on or occ.pen.purpose != "MATERNIDAD":
            fail("El nacimiento requiere ocupación activa de maternidad.")
        if day < occ.started_on:
            fail("El nacimiento precede a la ocupación de origen.", "INVALID_DATE", 422)
        if not Balance.objects.filter(occupation=occ, category="HEMBRA", quantity__gt=0).exists():
            fail("Seleccione el grupo reproductor con hembras de maternidad.")
        if p["live"] + p["stillborn"] == 0:
            fail("Ingrese nacidos vivos o natimortos.", "VALIDATION_ERROR", 422)
        # Birth cohort has its own known age and maternity provenance.
        if p["live"]:
            lot = CuyLot.objects.create(
                provenance=f"Nacimiento en {occ.pen.code}", opened_on=day,
                born_from=day, born_until=day, parent=occ.lot, source_occupation=occ,
            )
            baby = new_occupation(lot, occ.pen, day)
            changes.append((baby, "LACTANTE", "SIN_CLASIFICAR", p["live"]))
    elif kind == "CUY_DEATH":
        validate_items(p["items"])
        for i in p["items"]:
            changes.append((occupation(i.get("occupation_id")), i["category"], i["quality"], -i["quantity"]))
    elif kind == "CUY_WEAN":
        occ = occupation(p["occupation_id"])
        if occ.pen.purpose != "MATERNIDAD":
            fail("El destete debe salir de maternidad.")
        validate_items(p["destinations"])
        if sum(i["quantity"] for i in p["destinations"]) != p["quantity"]:
            fail("La salida debe ser igual a las entradas.", "UNBALANCED_MOVEMENT", 422)
        changes.append((occ, "LACTANTE", p["quality"], -p["quantity"]))
        child = CuyLot.objects.create(
            provenance=f"Destete de {occ.pen.code}", opened_on=day, parent=occ.lot,
            source_occupation=occ, born_from=occ.lot.born_from, born_until=occ.lot.born_until,
        )
        for i in p["destinations"]:
            dest = get(Pen, i.get("pen_id"))
            require_pen(actor, dest, write=True)
            if dest.shed.center_id != occ.pen.shed.center_id:
                fail("Destete entre centros: destete primero y luego despache.")
            if i["quality"] not in ["A", "B"] or dest.purpose != f"RECRIA_{'MACHOS' if i['category'] == 'MACHO' else 'HEMBRAS'}" or i["category"] == "LACTANTE":
                fail("Destete requiere machos/hembras A o B en recría compatible.", "INCOMPATIBLE_PURPOSE", 422)
            changes.append((new_occupation(child, dest, day), i["category"], i["quality"], i["quantity"]))
    elif kind in ["CUY_MOVE", "CUY_DISPATCH"]:
        source, dest = get(Pen, p["source_id"]), get(Pen, p["destination_id"])
        if source.id == dest.id:
            fail("Seleccione otra poza.", "VALIDATION_ERROR", 422)
        immediate = kind == "CUY_MOVE"
        if immediate and source.shed.center_id != dest.shed.center_id:
            fail("Entre centros se requiere salida y recepción.")
        if not immediate and source.shed.center_id == dest.shed.center_id:
            fail("Dentro de un centro utilice traslado inmediato.")
        validate_destination(actor, dest, immediate=immediate)
        changes = outgoing(p, source)
        items = [dict(lot_id=str(o.lot_id), category=cat, quality=q, quantity=-delta,
                      source_occupation_id=str(o.id)) for o, cat, q, delta in changes]
        check_arrival(dest, items)
        if immediate:
            changes += [(new_occupation(o.lot, dest, day), cat, q, -delta) for o, cat, q, delta in list(changes)]
        else:
            Transfer.objects.create(id=move.id, source=source, destination=dest,
                                    dispatched_by=actor, items=items)
    elif kind == "CUY_RECEIVE":
        transfer = Transfer.objects.select_for_update().get(pk=p["transfer_id"])
        if transfer.state != "EN_TRANSITO":
            fail("La cantidad en tránsito ya fue consumida.", "ALREADY_RECEIVED")
        if day < Movement.objects.get(pk=transfer.id).date:
            fail("La recepción no puede preceder a la salida.", "INVALID_DATE", 422)
        dest = get(Pen, transfer.destination_id)
        require_pen(actor, dest, write=True)
        check_arrival(dest, transfer.items)
        for i in transfer.items:
            lot = get(CuyLot, i["lot_id"])
            changes.append((new_occupation(lot, dest, day), i["category"], i["quality"], i["quantity"]))
        transfer.state, transfer.received_by, transfer.received_at = "RECIBIDO", actor, timezone.now()
        transfer.save()
    elif kind == "CUY_RECLASS":
        validate_items(p["items"])
        for i in p["items"]:
            occ = occupation(i.get("occupation_id"))
            if i["quality"] == p["new_quality"]:
                fail("La calidad anterior y nueva son iguales.", "VALIDATION_ERROR", 422)
            changes += [(occ, i["category"], i["quality"], -i["quantity"]),
                        (occ, i["category"], p["new_quality"], i["quantity"])]
    elif kind == "CUY_COUNT":
        return count_physical(actor, move, p)
    apply_lines(move, changes, controlled=kind not in ["CUY_OPEN", "CUY_BIRTH"])
    record(actor, "cuy_movement", move.id, kind, after={"lines": len(changes)},
           reason=p["reason"], operation=operation)
    return {"movement_id": str(move.id)}


def check_arrival(dest, items):
    if not dest.active or not dest.shed.active or dest.shed.center_id not in enabled_centers():
        fail("Destino no disponible.")
    for i in items:
        compatible(dest, i["category"])
    if total(dest) + sum(i["quantity"] for i in items) > dest.capacity:
        fail(f"Capacidad insuficiente en {dest.code}.", "CAPACITY_EXCEEDED")


def count_physical(actor, move, p):
    pen = get(Pen, p["pen_id"])
    if not PhysicalCount.objects.filter(pen=pen, opening=True).exists():
        fail("Registre primero la apertura física.")
    if PhysicalCount.objects.filter(pen=pen, opening=False, state="PENDIENTE").exists():
        fail("Revise primero el conteo pendiente.")
    validate_items(p["items"], positive=False)
    expected = defaultdict(int)
    rows = LedgerLine.objects.filter(occupation__pen=pen, movement__date__lte=move.date).values(
        "occupation_id", "category", "quality",
    ).annotate(n=Sum("delta"))
    for row in rows:
        expected[(str(row["occupation_id"]), row["category"], row["quality"])] = row["n"]
    observed = {}
    for i in p["items"]:
        occ = occupation(i.get("occupation_id"))
        if occ.pen_id != pen.id or occ.started_on > move.date:
            fail("Ocupación ajena o posterior al corte.", "VALIDATION_ERROR", 422)
        compatible(pen, i["category"])
        observed[(str(occ.id), i["category"], i["quality"])] = i["quantity"]
    count = PhysicalCount.objects.create(id=move.id, pen=pen, date=move.date, author=actor)
    difference = False
    for key in sorted(set(expected) | set(observed)):
        exp, obs = expected.get(key, 0), observed.get(key, 0)
        CountDetail.objects.create(count=count, occupation_id=key[0], category=key[1],
                                  quality=key[2], expected=exp, observed=obs)
        difference |= exp != obs
    if difference:
        notify(recipients=recipients(), type="CUY_DIFFERENCE", source_event_id=count.id,
               entity_type="cuy_pen", entity_id=pen.id, title="Diferencia de conteo",
               text=f"{pen.code}: conteo pendiente de revisión administrativa.")
    if sum(observed.values()) > pen.capacity:
        alert(pen, f"capacity:{pen.id}", "CAPACITY", f"{pen.code}: el conteo físico excede la capacidad.")
    record(actor, "cuy_count", count.id, "COUNT", reason=move.reason)
    return {"count_id": str(count.id)}


def review(actor, c, operation, day):
    require_admin(actor)
    p = c["payload"]
    count = get(PhysicalCount, p["count_id"])
    lock_scope([count.pen_id], day)
    count = PhysicalCount.objects.select_for_update().get(pk=count.id)
    if count.state != "PENDIENTE":
        fail("El conteo ya fue revisado.")
    # Subsequent counts cannot be applied on top of overlapping unreviewed cuts.
    if PhysicalCount.objects.filter(pen=count.pen, date__gt=count.date, state="APLICADO", opening=False).exists():
        fail("Existe un corte posterior aplicado; requiere revisión.", "COUNT_REVIEW_REQUIRED")
    if day < count.date:
        fail("La aprobación no puede preceder al corte.", "INVALID_DATE", 422)
    move = movement_for(actor, c, operation)
    if p["approve"]:
        changes = [
            (d.occupation, d.category, d.quality, d.difference)
            for d in count.details.select_related("occupation__pen__shed__center", "occupation__lot")
        ]
        # Keep the original cut immutable; only its delta is applied to today's balance.
        apply_lines(move, changes, controlled=False)
    count.state = "APLICADO" if p["approve"] else "RECHAZADO"
    count.reviewed_by, count.reviewed_at, count.reason = actor, timezone.now(), p["reason"]
    count.save()
    record(actor, "cuy_count", count.id, "REVIEW", after={"state": count.state}, reason=p["reason"])
    return {"count_id": str(count.id), "state": count.state}


def daily(actor, c, day):
    p, kind = c["payload"], c["type"]
    shed = get(Shed, p["shed_id"])
    lock_scope([], day, check_closed=False, extra_sheds=[shed.id])
    if kind == "CUY_REOPEN":
        require_admin(actor)
    else:
        require_shed(actor, shed)
    report, _ = DailyReport.objects.get_or_create(shed=shed, date=day)
    target = "ABIERTO" if kind == "CUY_REOPEN" else "CERRADO"
    if report.state == target:
        fail("El parte ya se encuentra en ese estado.")
    report.state = target
    if target == "CERRADO":
        report.responsible, report.closed_at = actor, timezone.now()
    report.save()
    DailyRevision.objects.create(report=report, actor=actor, action=kind.removeprefix("CUY_"), reason=p["reason"])
    record(actor, "cuy_daily", report.id, kind, after={"state": target}, reason=p["reason"])
    return {"report_id": str(report.id), "state": target}


def commands():
    return {kind: (serializer, handle, authorize) for kind, serializer in COMMANDS.items()}


@transaction.atomic
def configure(actor, p):
    from apps.accounts.models import RoleAssignment
    from apps.catalog.models import CenterProduct, Location, Product, Unit

    from .models import AlertPolicy, ShedGrant

    require_admin(actor)
    resource = p["resource"]
    schemas = {
        "enable": (CenterProduct, ["center_id"]),
        "shed": (Shed, ["center_id", "code", "name"]),
        "pen": (Pen, ["shed_id", "code", "capacity", "purpose"]),
        "grant": (ShedGrant, ["assignment_id", "shed_id"]),
        "policy": (AlertPolicy, ["center_id", "reproductive_months", "minimum_weaned_per_female"]),
    }
    model, fields = schemas[resource]
    missing = [f for f in fields if f not in p]
    if missing:
        fail(f"Faltan campos: {', '.join(missing)}.", "VALIDATION_ERROR", 422)
    allowed = set(fields) | {"resource", "id", "reason", "active"}
    if set(p) - allowed:
        fail("Campos incompatibles con el recurso.", "VALIDATION_ERROR", 422)
    if resource in ["enable", "shed", "policy"]:
        center = get(Location, p["center_id"])
        if center.kind != "CENTRO" or not center.active:
            fail("Seleccione un centro activo.", "VALIDATION_ERROR", 422)
        from .locking import lock_centers

        lock_centers([center.id])
        list(Location.objects.select_for_update().filter(pk=center.id))
        # Enabling/disabling the module must serialize with operational writes too.
        if resource == "enable":
            list(Shed.objects.select_for_update().filter(center=center).order_by("id"))
        if resource != "enable" and center.id not in enabled_centers():
            fail("Habilite Cuyes en el centro.")
    if resource in ["pen", "grant"]:
        shed = get(Shed, p["shed_id"])
        lock_scope([], timezone.localdate(), extra_sheds=[shed.id], check_closed=False)
        if shed.center_id not in enabled_centers() or not shed.active:
            fail("Galpón inactivo o Cuyes no habilitado.")
    obj = model.objects.select_for_update().filter(pk=p["id"]).first()
    if resource == "enable":
        Unit.objects.get_or_create(code="UN", defaults={"name": "Unidad"})
        product, _ = Product.objects.get_or_create(
            code="CUYES", defaults={"name": "Cuyes", "unit_id": "UN"},
        )
        if product.unit_id != "UN":
            fail("El producto CUYES debe usar UN.")
        existing = CenterProduct.objects.filter(center=center, product=product).first()
        if obj and (obj.center_id != center.id or obj.product_id != product.id):
            fail("El UUID pertenece a otra habilitación; no se reasigna.", "IDEMPOTENCY_CONFLICT")
        obj = existing or obj
        data = {"center": center, "product": product, "enabled": p["active"]}
        if p["active"]:
            AlertPolicy.objects.get_or_create(center=center)
    else:
        data = {f: p[f] for f in fields}
        if resource != "policy":
            data["active"] = p["active"]
    if resource == "grant":
        assignment = get(RoleAssignment, p["assignment_id"])
        if assignment.role_id != "GALPONERO" or assignment.location_id != shed.center_id or assignment.scope != "UBICACION":
            fail("La asignación GALPONERO debe pertenecer al centro del galpón.", "VALIDATION_ERROR", 422)
        if p["active"]:
            from apps.accounts.access import active_assignments

            if not active_assignments(assignment.user).filter(pk=assignment.id).exists():
                fail("La asignación GALPONERO no está vigente.", "VALIDATION_ERROR", 422)
    before = snapshot({f.attname: getattr(obj, f.attname) for f in obj._meta.fields}) if obj else {}
    if obj:
        for key in ["center_id", "shed_id", "assignment_id"]:
            if key in data and getattr(obj, key) != data[key]:
                fail("No se puede reasignar un registro histórico.", "VALIDATION_ERROR", 422)
    obj = obj or model(id=p["id"])
    for key, value in data.items():
        setattr(obj, key, value)
    if resource == "pen" and obj.pk and Balance.objects.filter(occupation__pen_id=obj.pk, quantity__gt=0).exists():
        for category in Balance.objects.filter(occupation__pen_id=obj.pk, quantity__gt=0).values_list("category", flat=True).distinct():
            compatible(obj, category)
    obj.full_clean()
    try:
        with transaction.atomic():
            obj.save()
    except IntegrityError:
        fail("Código o asignación duplicados.", "VALIDATION_ERROR", 422)
    after = snapshot({f.attname: getattr(obj, f.attname) for f in obj._meta.fields})
    if before != after:
        entry = record(actor, f"cuy_{resource}", obj.id, "CONFIGURE", before=before, after=after, reason=p["reason"])
        if resource in ["enable", "shed", "pen"]:
            from .sales_stock import detect_shortages

            center_id = obj.center_id if resource in ["enable", "shed"] else obj.shed.center_id
            detect_shortages([center_id], entry.id, actor)
    if resource == "pen" and total(obj) > obj.capacity:
        alert(obj, f"capacity:{obj.id}", "CAPACITY", f"{obj.code}: el saldo confirmado excede la nueva capacidad.")
    return after
