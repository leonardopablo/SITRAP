from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import F, Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import is_admin, location_ids
from apps.catalog.models import AnimalStay
from apps.common.errors import DomainError, ErrorSerializer
from apps.milk.models import MilkingDetail

from .common import PeriodQuery, bounded, decimal, metadata, snapshot


class MilkQuery(PeriodQuery):
    animal_id = serializers.UUIDField(required=False)
    turn_id = serializers.UUIDField(required=False)


class MilkRecord(serializers.Serializer):
    milking_id = serializers.UUIDField()
    version_id = serializers.UUIDField()
    center_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    date = serializers.DateField()
    turn_id = serializers.UUIDField()
    animal_id = serializers.UUIDField()
    liters = serializers.DecimalField(max_digits=20, decimal_places=3)


class AnimalMetric(serializers.Serializer):
    animal_id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    recorded_days = serializers.IntegerField()
    days_present = serializers.IntegerField()
    days_without_record = serializers.IntegerField()
    average_per_recorded_day = serializers.DecimalField(
        max_digits=20, decimal_places=3, allow_null=True
    )


class MilkDay(serializers.Serializer):
    date = serializers.DateField()
    liters = serializers.DecimalField(max_digits=20, decimal_places=3, allow_null=True)
    recorded_animals = serializers.IntegerField()


class MilkMetrics(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    cutoff = serializers.DateTimeField()
    timezone = serializers.CharField()
    synchronized_only = serializers.BooleanField()
    liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    recorded_days = serializers.IntegerField()
    average_per_recorded_day = serializers.DecimalField(
        max_digits=20, decimal_places=3, allow_null=True
    )
    animals = AnimalMetric(many=True)
    days = MilkDay(many=True)
    records = MilkRecord(many=True)


def milk_metrics(actor, filters):
    centers = None if is_admin(actor) else list(location_ids(actor, "PRODUCCION"))
    if centers == [] or (
        centers is not None and filters.get("center_id") and filters["center_id"] not in centers
    ):
        raise DomainError("PERMISSION_DENIED", "Sin acceso a producción en ese centro.", 403)
    start, end = filters["date_from"], filters["date_to"]
    stays = AnimalStay.objects.filter(
        starts_on__lte=end, animal__sex="HEMBRA", animal__species__code="BOVINO"
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gt=start))
    details = MilkingDetail.objects.filter(
        version_id=F("version__production__current_version_id"),
        version__production__state="CONFIRMADA",
        version__production__milking__date__range=(start, end),
    )
    if centers is not None:
        stays = stays.filter(center_id__in=centers)
        details = details.filter(version__production__center_id__in=centers)
    if "center_id" in filters:
        stays = stays.filter(center_id=filters["center_id"])
        details = details.filter(version__production__center_id=filters["center_id"])
    if "product_id" in filters:
        details = details.filter(version__production__product_id=filters["product_id"])
        stays = stays.filter(center__centerproduct__product_id=filters["product_id"])
    for key in ("animal_id", "turn_id"):
        if key in filters:
            details = details.filter(
                **{
                    key if key == "animal_id" else "version__production__milking__turn_id": filters[
                        key
                    ]
                }
            )
    if "animal_id" in filters:
        stays = stays.filter(animal_id=filters["animal_id"])
    animals, present, recorded, quantities = (
        {},
        defaultdict(set),
        defaultdict(set),
        defaultdict(Decimal),
    )
    for stay in bounded(stays.select_related("animal").distinct()):
        animals[stay.animal_id] = stay.animal
        lo, hi = (
            max(start, stay.starts_on),
            min(end + timedelta(days=1), stay.ends_on or end + timedelta(days=1)),
        )
        present[stay.animal_id].update(lo + timedelta(days=i) for i in range((hi - lo).days))
    records, day_animals, day_liters = [], defaultdict(set), defaultdict(Decimal)
    for detail in bounded(
        details.select_related("animal", "version__production__milking").order_by(
            "version__production__milking__date", "animal_id", "id"
        )
    ):
        milking = detail.version.production.milking
        animals[detail.animal_id] = detail.animal
        # Only confirmed versions participate; NULL in drafts is never converted to zero.
        if detail.liters is None:
            continue
        recorded[detail.animal_id].add(milking.date)
        present[detail.animal_id].add(milking.date)
        quantities[detail.animal_id] += detail.liters
        day_liters[milking.date] += detail.liters
        day_animals[milking.date].add(detail.animal_id)
        records.append(
            dict(
                milking_id=milking.id,
                version_id=detail.version_id,
                center_id=milking.center_id,
                product_id=detail.version.production.product_id,
                date=milking.date,
                turn_id=milking.turn_id,
                animal_id=detail.animal_id,
                liters=decimal(detail.liters),
            )
        )
    total = sum(quantities.values(), Decimal(0))
    return {
        **metadata(filters),
        "liters": decimal(total),
        "recorded_days": len(day_liters),
        "average_per_recorded_day": decimal(total / len(day_liters) if day_liters else None),
        "animals": [
            dict(
                animal_id=id,
                code=animal.code,
                name=animal.name,
                liters=decimal(quantities[id]),
                recorded_days=len(recorded[id]),
                days_present=len(present[id]),
                days_without_record=len(present[id] - recorded[id]),
                average_per_recorded_day=decimal(
                    quantities[id] / len(recorded[id]) if recorded[id] else None
                ),
            )
            for id, animal in sorted(animals.items(), key=lambda pair: pair[1].code)
        ],
        "days": [
            dict(
                date=day,
                liters=decimal(day_liters[day]) if day in day_liters else None,
                recorded_animals=len(day_animals[day]),
            )
            for day in (start + timedelta(days=i) for i in range((end - start).days + 1))
        ],
        "records": records,
    }


class MilkMetricsView(APIView):
    @extend_schema(
        parameters=[MilkQuery],
        responses={200: MilkMetrics, 403: ErrorSerializer, 422: ErrorSerializer},
    )
    @snapshot
    def get(self, request):
        query = MilkQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(milk_metrics(request.user, query.validated_data))
