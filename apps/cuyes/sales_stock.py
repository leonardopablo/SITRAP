from collections import defaultdict
from uuid import NAMESPACE_URL, uuid5

from django.db.models import F, Q, Sum
from django.utils import timezone

from .access import enabled_centers
from .models import Balance, DispatchSelection, ReservationDetail, SaleOrder, SaleReservation


def live_reservations():
    return SaleReservation.objects.filter(
        Q(state="PAGADA") | Q(state="IMPAGA", expires_at__gt=timezone.now()),
    )


def stock(center_id, *, pens=None):
    query = Balance.objects.filter(
        occupation__pen__shed__center_id=center_id, occupation__pen__active=True,
        occupation__pen__shed__active=True, occupation__pen__shed__center_id__in=enabled_centers(),
    )
    if pens is not None:
        query = query.filter(occupation__pen__in=pens)
    return {
        (r["category"], r["quality"]): r["n"]
        for r in query.values("category", "quality").annotate(n=Sum("quantity"))
    }


def commitments(center_id, *, exclude_order=None):
    query = ReservationDetail.objects.filter(reservation__in=live_reservations(), reservation__center_id=center_id)
    if exclude_order:
        query = query.exclude(reservation__order_id=exclude_order)
    return {
        (r["category"], r["quality"]): r["n"]
        for r in query.values("category", "quality").annotate(n=Sum("quantity"))
    }


def available(center_id, *, pens=None, exclude_order=None):
    physical, reserved = stock(center_id, pens=pens), commitments(center_id, exclude_order=exclude_order)
    return {key: max(0, physical.get(key, 0) - reserved.get(key, 0)) for key in set(physical) | set(reserved)}


def demand(order):
    result = defaultdict(int)
    for line in order.lines.all():
        for component in line.recipe:
            result[(component["category"], component["quality"])] += line.units * component["quantity"]
    return dict(result)


def active_selections(*, exclude_order=None):
    query = DispatchSelection.objects.filter(
        preparation_id=F("preparation__order__preparation_id"),
        preparation__order__state__in=["PAGADO", "EN_PREPARACION"],
    )
    if exclude_order:
        query = query.exclude(preparation__order_id=exclude_order)
    return query


def claimed_buckets(*, exclude_order=None):
    return {
        (str(r["occupation_id"]), r["category"], r["quality"]): r["n"]
        for r in active_selections(exclude_order=exclude_order).values(
            "occupation_id", "category", "quality",
        ).annotate(n=Sum("quantity"))
    }


def shortage_keys(center_id):
    physical, reserved = stock(center_id), commitments(center_id)
    return {key for key, n in reserved.items() if n > physical.get(key, 0)}


def selection_missing(order):
    if not order.preparation_id:
        return False
    buckets = defaultdict(int)
    for line in order.preparation.selections.select_related("occupation__pen__shed"):
        if not line.occupation.pen.active or not line.occupation.pen.shed.active:
            return True
        buckets[(line.occupation_id, line.category, line.quality)] += line.quantity
    all_claims = claimed_buckets()
    for (occupation_id, category, quality), quantity in buckets.items():
        actual = Balance.objects.filter(occupation_id=occupation_id, category=category, quality=quality).first()
        if not actual or actual.quantity < max(quantity, all_claims.get((str(occupation_id), category, quality), 0)):
            return True
    return False


def detect_shortages(center_ids, source_event, actor=None):
    """Runs under the shared center lock, inside the physical movement transaction."""
    from .sales_notifications import sale_notice

    for center_id in sorted(set(center_ids), key=str):
        keys = shortage_keys(center_id)
        orders = SaleOrder.objects.select_for_update().filter(
            center_id=center_id, state__in=["RESERVADO", "PAGADO", "EN_PREPARACION"],
        ).order_by("id")
        for order in orders:
            affected = bool(keys & set(demand(order))) or selection_missing(order)
            if affected and not order.shortage:
                order.shortage = True
                order.confirmation_round += 1
                order.version += 1
                order.save()
                if actor:
                    from apps.audit.services import record

                    record(actor, "cuy_sale", order.id, "SALE_STOCK_SHORTAGE",
                           after={"shortage": True, "source_event": str(source_event)})
                sale_notice(order, "SALE_SHORTAGE", uuid5(NAMESPACE_URL, f"{source_event}:{order.id}:shortage"))
