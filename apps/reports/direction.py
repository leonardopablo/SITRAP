from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import active_assignments
from apps.catalog.models import AnimalStay, CenterProduct, Location
from apps.common.errors import DomainError, ErrorSerializer
from apps.common.serializers import StrictSerializer
from apps.cuyes.models import Alert, LedgerLine, Movement, Occupation, Pen, PhysicalCount, SaleOrder
from apps.milk.models import Milking, MilkingDetail
from apps.traceability.models import Conformity, Transfer


class DirectionQuery(StrictSerializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    center_id = serializers.UUIDField(required=False)


class DirectionOutput(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()
    refreshed_at = serializers.DateTimeField()
    demo = serializers.BooleanField()
    centers = serializers.ListField(child=serializers.DictField())
    results = serializers.ListField(child=serializers.DictField())


def actor_key(user):
    return (user.id, user.name or user.username)


def center_report(center, start, end):
    activity = defaultdict(lambda: dict(milkings=0, milk_liters=Decimal(0), milk_pickups=0,
                                        milk_receptions=0, cuy_records=0, cuy_pickups=0))
    products = set(CenterProduct.objects.filter(center=center, enabled=True, product__active=True)
                   .values_list("product__code", "product__unit_id"))
    milk = MilkReport(center, start, end, activity)
    cuyes = cuy_report(center, start, end, activity)
    return {
        "id": center.id, "name": center.name,
        "milk": milk.data if milk.applicable or any(unit == "L" for _, unit in products) else None,
        "cuyes": cuyes if cuyes["pens"] or ("CUYES", "UN") in products else None,
        "activity": [{"id": key[0], "name": key[1], **counts, "milk_liters": str(counts["milk_liters"])} for key, counts in
                     sorted(activity.items(), key=lambda row: (row[0][1], row[0][0]))],
    }


class MilkReport:
    def __init__(self, center, start, end, activity):
        milkings = list(Milking.objects.filter(center=center, date__range=(start, end),
                         voided_at__isnull=True, production__state="CONFIRMADA",
                         production__current_version__state="PUBLICADA")
                        .select_related("production__current_version", "production__responsible", "turn"))
        cows = AnimalStay.objects.filter(center=center, starts_on__lte=end, animal__species__code="BOVINO",
                                         animal__sex="HEMBRA").filter(Q(ends_on__gt=start) | Q(ends_on__isnull=True))
        animals = {}
        for stay in cows.select_related("animal"):
            animals[stay.animal_id] = [stay.animal.code, stay.animal.name, Decimal(0), 0]
        for detail in MilkingDetail.objects.filter(
            version_id__in=[m.production.current_version_id for m in milkings], liters__isnull=False,
        ).select_related("animal"):
            row = animals.setdefault(detail.animal_id, [detail.animal.code, detail.animal.name, Decimal(0), 0])
            row[2] += detail.liters
            row[3] += 1
        series, turns = defaultdict(Decimal), defaultdict(Decimal)
        for m in milkings:
            quantity = m.production.current_version.quantity
            series[m.date.isoformat()[:7]] += quantity
            turns[m.turn.name] += quantity
            person = activity[actor_key(m.production.responsible)]
            person["milkings"] += 1
            person["milk_liters"] += quantity
        transfers, pending, sent, received, paired = self.trace(center, start, end, activity)
        self.applicable = bool(milkings or animals or transfers or pending)
        self.data = dict(
            milkings=len(milkings), liters=str(sum(series.values(), Decimal(0))),
            monthly={k: str(v) for k, v in sorted(series.items())},
            turns={k: str(v) for k, v in sorted(turns.items())},
            cows=[dict(code=r[0], name=r[1], liters=str(r[2]) if r[3] else None, records=r[3])
                  for r in sorted(animals.values(), key=lambda row: row[0])],
            sent=str(sent), received=str(received), reception_difference=str(paired),
            pending=pending, trace=transfers,
        )

    @staticmethod
    def trace(center, start, end, activity):
        deeds = Conformity.objects.filter(version__origin=center, stage__in=["RECOGIDA", "RECEPCION"],
                                          occurred_at__date__range=(start, end)).select_related("user")
        ids = set(deeds.values_list("version__transfer_id", flat=True))
        q = Transfer.objects.filter(current_version__origin=center).exclude(state__in=["BORRADOR", "CANCELADO"])
        pending = q.filter(state__in=["PENDIENTE_RECOGIDA", "EN_CAMINO"]).count()
        for item in deeds:
            field = "milk_pickups" if item.stage == "RECOGIDA" else "milk_receptions"
            activity[actor_key(item.user)][field] += 1
        sent = received = paired = Decimal(0)
        trace = []
        for t in q.filter(Q(id__in=ids) | Q(current_version__published_at__date__range=(start, end))).select_related(
            "current_version__destination", "current_version__driver",
        ).prefetch_related("current_version__lines__lot__production__milking",
                           "current_version__conformities__details"):
            v = t.current_version
            events = {event.stage: event for event in v.conformities.all()}
            pickup, reception = events.get("RECOGIDA"), events.get("RECEPCION")
            planned = sum((line.quantity for line in v.lines.all()), Decimal(0))
            departed = (sum((detail.accepted_quantity for detail in pickup.details.all()), Decimal(0))
                        if pickup else None)
            arrived = (sum((detail.accepted_quantity for detail in reception.details.all()), Decimal(0))
                       if reception else None)
            if pickup and start <= timezone.localdate(pickup.occurred_at) <= end:
                sent += departed
            if reception and start <= timezone.localdate(reception.occurred_at) <= end:
                received += arrived
                if departed is not None:
                    paired += arrived - departed
            trace.append(dict(code=t.code, state=t.state, destination=v.destination.name,
                              driver=v.driver.name or v.driver.username, requested=v.published_at,
                              pickup=pickup.occurred_at if pickup else None,
                              reception=reception.occurred_at if reception else None,
                              planned=str(planned), sent=str(departed) if pickup else None,
                              received=str(arrived) if reception else None,
                              lots=[dict(code=line.lot.code, date=line.lot.production.milking.date,
                                         liters=str(line.quantity)) for line in v.lines.all()]))
        return sorted(trace, key=lambda r: r["requested"] or r["pickup"] or timezone.now(), reverse=True), pending, sent, received, paired


def cuy_report(center, start, end, activity):
    pens = {p.id: p for p in Pen.objects.filter(shed__center=center).select_related("shed").order_by("code")}
    occupation_pens = dict(Occupation.objects.filter(pen_id__in=pens).values_list("id", "pen_id"))
    birth_pens = {str(k): v for k, v in occupation_pens.items()}
    stock, days_delta = defaultdict(int), defaultdict(int)
    monthly = defaultdict(lambda: dict(births=0, stillborn=0, deaths=0, weaned=0, population=0))
    metrics = dict(births=0, stillborn=0, deaths=0, weaned=0, moved=0, dispatched=0, received=0,
                   adjusted=0, reclassified=0)
    recorded = set()
    for line in LedgerLine.objects.filter(occupation_id__in=occupation_pens, movement__date__lte=end).select_related(
        "movement__compensates", "movement__actor",
    ):
        move = line.movement
        stock[occupation_pens[line.occupation_id], line.category, line.quality] += line.delta
        days_delta[move.date] += line.delta
        if move.date < start:
            continue
        if move.id not in recorded:
            activity[actor_key(move.actor)]["cuy_records"] += 1
            recorded.add(move.id)
        kind = (move.compensates or move).kind
        original_delta = -line.delta if move.compensates_id else line.delta
        metric = None
        if kind == "DEATH":
            metric = "deaths"
        elif kind == "WEAN" and line.category == "LACTANTE":
            metric = "weaned"
        elif kind == "MOVE" and original_delta < 0:
            metric = "moved"
        elif kind == "DISPATCH":
            metric = "dispatched"
        elif kind == "RECLASS" and original_delta < 0:
            metric = "reclassified"
        if metric:
            metrics[metric] -= line.delta
            if metric in ("deaths", "weaned"):
                monthly[move.date.isoformat()[:7]][metric] -= line.delta
        if kind in ("RECEIVE", "REVIEW"):
            metrics["received" if kind == "RECEIVE" else "adjusted"] += line.delta
    for move in Movement.objects.filter(date__range=(start, end)).filter(
        Q(kind="BIRTH") | Q(compensates__kind="BIRTH")
    ).select_related("compensates", "actor"):
        original = move.compensates or move
        if str(original.metadata.get("occupation_id")) not in birth_pens:
            continue
        if move.id not in recorded:
            activity[actor_key(move.actor)]["cuy_records"] += 1
        for field, key in (("births", "live"), ("stillborn", "stillborn")):
            n = original.metadata.get(key, 0) * (-1 if move.compensates_id else 1)
            metrics[field] += n
            monthly[move.date.isoformat()[:7]][field] += n
    population = sum(n for day, n in days_delta.items() if day < start)
    animal_days, days = 0, (end - start).days + 1
    for i in range(days):
        day = start + timedelta(days=i)
        population += days_delta[day]
        animal_days += population
        monthly[day.isoformat()[:7]]["population"] = population
    opened = PhysicalCount.objects.filter(pen_id__in=pens, opening=True)
    coverage = opened.filter(date__lte=start).values("pen_id").distinct().count()
    applicable_pens = opened.filter(date__lte=end).values("pen_id").distinct().count()
    average = animal_days / days if applicable_pens and coverage == applicable_pens and animal_days > 0 else None
    trace, sale_summary = sale_report(center, start, end, activity)
    return dict(**metrics, population=population, average_population=round(average, 2) if average else None,
                mortality_rate=round(metrics["deaths"] * 100 / average, 2) if average and metrics["deaths"] >= 0 else None,
                birth_rate=round(metrics["births"] * 100 / average, 2) if average and metrics["births"] >= 0 else None,
                stillborn_rate=round(metrics["stillborn"] * 100 / (metrics["births"] + metrics["stillborn"]), 2)
                if metrics["births"] >= 0 and metrics["stillborn"] >= 0 and metrics["births"] + metrics["stillborn"] else None,
                monthly=dict(sorted(monthly.items())),
                pending_counts=PhysicalCount.objects.filter(pen_id__in=pens, state="PENDIENTE").count(),
                alerts=Alert.objects.filter(pen_id__in=pens, resolved_at__isnull=True).count(),
                pens=[dict(shed=p.shed.code, code=p.code, purpose=p.get_purpose_display(), capacity=p.capacity,
                           population=sum(n for (pk, _, _), n in stock.items() if pk == p.id),
                           composition=[dict(category=c, quality=q, quantity=n)
                                        for (pk, c, q), n in sorted(stock.items()) if pk == p.id and n])
                      for p in pens.values()],
                sales=sale_summary, trace=trace)


def sale_report(center, start, end, activity):
    orders = SaleOrder.objects.filter(center=center)
    pending = orders.filter(state__in=["SOLICITADO", "AJUSTE_PENDIENTE", "RESERVADO", "PAGADO",
                                       "EN_PREPARACION", "EN_RUTA", "EN_PUNTO"]).exclude(
        state="RESERVADO", reservations__state="IMPAGA", reservations__expires_at__lte=timezone.now(),
    ).count()
    selected = orders.filter(Q(created_at__date__range=(start, end)) |
                             Q(payment__validated_at__date__range=(start, end)) |
                             Q(reservations__expires_at__date__range=(start, end)) |
                             Q(dispatch__departed_at__date__range=(start, end)) |
                             Q(deliveries__registered_at__date__range=(start, end))).distinct()
    trace, units, delivered, expired = [], 0, 0, 0
    revenues = defaultdict(Decimal)
    for o in selected.select_related("dispatch__actor", "driver", "point", "payment").prefetch_related(
        "dispatch__details", "deliveries__registered_by", "reservations",
    ).order_by("-created_at"):
        shipment = getattr(o, "dispatch", None)
        facts = list(o.deliveries.all())
        delivered += sum(f.stage == "ENTREGA_CLIENTE" and start <= timezone.localdate(f.registered_at) <= end
                         for f in facts)
        expired += sum(start <= timezone.localdate(r.expires_at) <= end and
                       (r.state == "VENCIDA" or (r.state == "IMPAGA" and r.expires_at <= timezone.now()))
                       for r in o.reservations.all())
        payment = getattr(o, "payment", None)
        if payment and start <= timezone.localdate(payment.validated_at) <= end:
            revenues[payment.currency] += payment.amount
        origins = []
        if shipment:
            origins = [dict(shed=d.snapshot.get("shed"), pen=d.snapshot.get("pen"),
                            lot=str(d.snapshot.get("lot_id", ""))[:8], category=d.category, quality=d.quality,
                            quantity=d.quantity) for d in shipment.details.all()]
            if start <= timezone.localdate(shipment.departed_at) <= end:
                units += sum(d["quantity"] for d in origins)
                if o.driver and o.mode == "PUNTO":
                    activity[actor_key(o.driver)]["cuy_pickups"] += 1
        trace.append(dict(code=o.code[:12], state=o.state, mode=o.mode, point=o.point.name if o.point else None,
                          dispatched_at=shipment.departed_at if shipment else None,
                          registered_at=o.created_at, origins=origins,
                          delivery=[dict(stage=f.stage, performed_by=f.physical_responsible,
                                         registered_by=f.registered_by.name or f.registered_by.username,
                                         time=f.registered_at) for f in facts]))
    return trace, dict(pending=pending, dispatched_units=units, delivered=delivered, expired=expired,
                       validated_payments={k: str(v) for k, v in sorted(revenues.items())})


class DirectionView(APIView):
    @extend_schema(parameters=[DirectionQuery],
                   responses={200: DirectionOutput, 403: ErrorSerializer, 422: ErrorSerializer})
    def get(self, request):
        if not active_assignments(request.user).filter(role_id__in=["ADMIN", "DIRECTOR"], scope="GLOBAL").exists():
            raise DomainError("PERMISSION_DENIED", "Se requiere Dirección o Administración.", 403)
        params = DirectionQuery(data=request.query_params)
        params.is_valid(raise_exception=True)
        p = params.validated_data
        today = timezone.localdate()
        end = p.get("end", today)
        start = p.get("start", end.replace(month=1, day=1))
        if start > end or end > today or (end - start).days > 366:
            raise DomainError("VALIDATION_ERROR", "Selecciona un período de hasta 367 días sin fechas futuras.", 422)
        centers = list(Location.objects.filter(kind="CENTRO", active=True))
        selected = [c for c in centers if not p.get("center_id") or c.id == p["center_id"]]
        if not selected and p.get("center_id"):
            raise DomainError("VALIDATION_ERROR", "Centro no disponible.", 422)
        from django.db import connection

        response = Response(dict(start=start, end=end, refreshed_at=timezone.now(),
                                 demo=connection.settings_dict["NAME"].startswith("sitrap_demo_"),
                                 centers=[dict(id=c.id, name=c.name) for c in centers],
                                 results=[center_report(c, start, end) for c in selected]))
        response["Cache-Control"] = "no-store, private"
        return response
