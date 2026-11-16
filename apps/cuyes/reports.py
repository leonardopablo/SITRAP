from collections import defaultdict
from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from .access import pens_for, sheds_for
from .models import (
    Alert,
    AlertPolicy,
    DailyReport,
    LedgerLine,
    Movement,
    Occupation,
    Pen,
    PhysicalCount,
    ShedGrant,
    Transfer,
)


def lot_data(lot):
    today = timezone.localdate()
    return {
        "id": lot.id, "provenance": lot.provenance, "parent_id": lot.parent_id,
        "source_occupation_id": lot.source_occupation_id, "opened_on": lot.opened_on,
        "born_from": lot.born_from, "born_until": lot.born_until, "installed_on": lot.installed_on,
        "age_days_min": (today - (lot.born_until or lot.born_from)).days if lot.born_from else None,
        "age_days_max": (today - lot.born_from).days if lot.born_from else None,
        "rearing_days": (today - lot.opened_on).days,
        "reproductive_days": (today - lot.installed_on).days if lot.installed_on else None,
    }


def pen_data(pen):
    occupations = []
    totals = {"MACHO": 0, "HEMBRA": 0, "LACTANTE": 0}
    for occ in Occupation.objects.filter(pen=pen).select_related("lot").order_by("started_on", "id"):
        balances = list(occ.balances.order_by("category", "quality").values("category", "quality", "quantity"))
        for b in balances:
            totals[b["category"]] += b["quantity"]
        occupations.append({
            "id": occ.id, "started_on": occ.started_on, "closed_on": occ.closed_on,
            "lot": lot_data(occ.lot), "balances": balances,
        })
    last_count = PhysicalCount.objects.filter(pen=pen).order_by("-date", "-registered_at").first()
    last_report = DailyReport.objects.filter(shed=pen.shed, state="CERRADO").order_by("-date").first()
    return {
        "id": pen.id, "code": pen.code, "shed_id": pen.shed_id, "shed": pen.shed.name,
        "center_id": pen.shed.center_id, "center": pen.shed.center.name,
        "capacity": pen.capacity, "purpose": pen.purpose, "active": pen.active,
        "population": sum(totals.values()), "totals": totals,
        "overcapacity": sum(totals.values()) > pen.capacity, "occupations": occupations,
        "last_count": last_count.date if last_count else None,
        "last_close": last_report.date if last_report else None,
    }


def ledger_data(move, allowed_pens):
    # A movement can touch several sheds. Never expose its full original payload
    # through a remaining authorized line after one of those sheds is revoked.
    public_metadata = {
        key: value for key, value in move.metadata.items()
        if key in {"live", "stillborn", "cause", "occupation_id", "transfer_id", "order_id",
                   "source_id", "destination_id", "source_id_snapshot",
                   "destination_id_snapshot", "pen_id_snapshot"}
    }
    return {
        "id": move.id, "kind": move.kind, "date": move.date, "registered_at": move.registered_at,
        "actor": move.actor.name, "reason": move.reason, "compensates_id": move.compensates_id,
        "metadata": public_metadata,
        "lines": list(move.lines.filter(occupation__pen__in=allowed_pens).values(
            "id", "occupation_id", "category", "quality", "delta", "snapshot",
        )),
    }


def scoped_transfers(actor):
    ids = pens_for(actor).values("id")
    return Transfer.objects.filter(Q(source_id__in=ids) | Q(destination_id__in=ids)).select_related("source", "destination")


def transfer_data(t):
    return {
        "id": t.id, "source_id": t.source_id, "source": t.source.code,
        "destination_id": t.destination_id, "destination": t.destination.code,
        "state": t.state, "items": t.items, "dispatched_at": t.dispatched_at,
        "received_at": t.received_at, "dispatched_by_id": t.dispatched_by_id,
        "received_by_id": t.received_by_id,
    }


def indicator(pen, start, end):
    opening = PhysicalCount.objects.filter(pen=pen, opening=True, date__lte=start).exists()
    lines = LedgerLine.objects.filter(occupation__pen=pen)
    before = lines.filter(category="HEMBRA", movement__date__lt=start).aggregate(n=Sum("delta"))["n"] or 0
    female_changes = defaultdict(int)
    for day, delta in lines.filter(category="HEMBRA", movement__date__range=[start, end]).values_list("movement__date", "delta"):
        female_changes[day] += delta
    animal_days, females = 0, before
    days = (end - start).days + 1
    for d in range(days):
        females += female_changes[start + timedelta(days=d)]
        animal_days += females
    average = animal_days / days
    moves = Movement.objects.filter(date__range=[start, end])
    live = stillborn = 0
    # Births with no live lines (all stillborn) still belong to the maternity pen.
    for move in moves.filter(Q(kind="BIRTH") | Q(compensates__kind="BIRTH")).select_related("compensates"):
        original = move.compensates if move.compensates_id else move
        occ = Occupation.objects.filter(pk=original.metadata.get("occupation_id"), pen=pen).first()
        if occ:
            sign = -1 if move.compensates_id else 1
            live += sign * original.metadata["live"]
            stillborn += sign * original.metadata["stillborn"]
    net = lines.filter(movement__date__range=[start, end])
    # Compensatory lines cancel the same indicator, attributed to the original operation.
    mortality = -(net.filter(Q(movement__kind="DEATH") | Q(movement__compensates__kind="DEATH")).aggregate(n=Sum("delta"))["n"] or 0)
    weaned = -(net.filter(category="LACTANTE").filter(
        Q(movement__kind="WEAN") | Q(movement__compensates__kind="WEAN"),
    ).aggregate(n=Sum("delta"))["n"] or 0)
    ratio = weaned / average if opening and average > 0 else None
    return {
        "pen_id": pen.id, "pen": pen.code, "start": start, "end": end,
        "live": live, "stillborn": stillborn, "mortality": mortality, "weaned": weaned,
        "average_females": round(average, 3) if opening else None,
        "weaned_per_female": round(ratio, 3) if ratio is not None else None,
        "coverage": opening, "status": "calculado" if ratio is not None else "datos insuficientes",
    }


def dashboard(actor, query):
    today = timezone.localdate()
    start = query.get("start", today.replace(day=1))
    end = query.get("end", today)
    if end < start or (end - start).days > 366:
        from .services import fail

        fail("Período no válido.", "VALIDATION_ERROR", 422)
    pens = pens_for(actor)
    for field in ["pen_id", "shed_id", "center_id"]:
        if query.get(field):
            lookup = {"pen_id": "id", "shed_id": "shed_id", "center_id": "shed__center_id"}[field]
            pens = pens.filter(**{lookup: query[field]})
    data = [pen_data(p) for p in pens.order_by("code")]
    transfers = scoped_transfers(actor).filter(state="EN_TRANSITO").filter(
        Q(source__in=pens) | Q(destination__in=pens),
    ).distinct()
    return {
        "updated_at": timezone.now(), "population": sum(p["population"] for p in data),
        "in_transit": sum(sum(i["quantity"] for i in t.items) for t in transfers),
        "pens": data, "indicators": [indicator(p, start, end) for p in pens if p.purpose == "MATERNIDAD"],
        "alerts": list(Alert.objects.filter(pen__in=pens, resolved_at__isnull=True).values()),
    }


def refresh_alerts(day):
    from .services import alert

    for policy in AlertPolicy.objects.select_related("center"):
        for pen in Pen.objects.filter(shed__center=policy.center, active=True).select_related("shed__center"):
            for occ in Occupation.objects.filter(pen=pen, closed_on__isnull=True, lot__installed_on__isnull=False).select_related("lot"):
                installed = occ.lot.installed_on
                months = (day.year - installed.year) * 12 + day.month - installed.month - (day.day < installed.day)
                if months >= policy.reproductive_months:
                    alert(pen, f"reproductive:{occ.lot_id}", "REPRODUCTIVE_AGE",
                          f"{pen.code}: lote con {months} meses desde instalación. Revisar; no se reclasifica automáticamente.")
            # Only complete calendar months are compared to the configured threshold.
            end = day.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
            metric = indicator(pen, start, end)
            ratio = metric["weaned_per_female"]
            if pen.purpose == "MATERNIDAD" and ratio is not None and ratio < float(policy.minimum_weaned_per_female):
                alert(pen, f"performance:{pen.id}:{start}", "LOW_PERFORMANCE",
                      f"{pen.code}: {ratio} destetados/hembra en {start:%Y-%m}; revisar manejo.")


def sync_entries(actor):
    for shed in sheds_for(actor):
        yield "cuy_shed", shed.id, {
            "id": shed.id, "center_id": shed.center_id, "code": shed.code,
            "name": shed.name, "active": shed.active,
        }
    for pen in pens_for(actor):
        yield "cuy_pen", pen.id, pen_data(pen)
    # No foreign destination details are copied for offline birth/death.


def scope_data(actor):
    return list(ShedGrant.objects.filter(
        assignment__user=actor,
    ).order_by("id").values("id", "assignment_id", "shed_id", "active")) + [
        {"shed": str(s.id), "active": s.active} for s in sheds_for(actor).order_by("id")
    ]
