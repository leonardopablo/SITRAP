from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import active_assignments, is_admin, location_ids
from apps.common.errors import DomainError, ErrorSerializer
from apps.traceability.models import Conformity, Correction
from apps.traceability.reads import scoped_transfers

from .common import PeriodQuery, bounded, decimal, metadata, snapshot


class TransferQuery(PeriodQuery):
    destination_id = serializers.UUIDField(required=False)


class TransferMetricRow(serializers.Serializer):
    transfer_id = serializers.UUIDField()
    code = serializers.CharField()
    version_id = serializers.UUIDField()
    version_number = serializers.IntegerField()
    origin_id = serializers.UUIDField()
    origin_name = serializers.CharField()
    destination_id = serializers.UUIDField()
    destination_name = serializers.CharField()
    state = serializers.CharField()
    liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    corrected = serializers.BooleanField()
    pickup_at = serializers.DateTimeField(allow_null=True)
    reception_at = serializers.DateTimeField(allow_null=True)
    pickup_in_period = serializers.BooleanField()
    reception_in_period = serializers.BooleanField()


class TransferDay(serializers.Serializer):
    date = serializers.DateField()
    picked_up_liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    received_liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    picked_up_count = serializers.IntegerField()
    received_count = serializers.IntegerField()


class TransferMetrics(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    cutoff = serializers.DateTimeField()
    timezone = serializers.CharField()
    synchronized_only = serializers.BooleanField()
    picked_up_liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    received_liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    picked_up_count = serializers.IntegerField()
    received_count = serializers.IntegerField()
    days = TransferDay(many=True)
    records = TransferMetricRow(many=True)


def report_transfers(actor, purpose=None):
    if not active_assignments(actor).exists():
        raise DomainError("PERMISSION_DENIED", "Sin ámbito vigente.", 403)
    query = scoped_transfers(actor).exclude(state__in=["BORRADOR", "CANCELADO"])
    if is_admin(actor) or purpose is None:
        return query
    p = Q(current_version__origin_id__in=location_ids(actor, "PRODUCCION"))
    t = Q(current_version__origin_id__in=location_ids(actor, "TRANSPORTE")) & (
        Q(current_version__driver=actor)
        | Q(versions__conformities__user=actor, versions__conformities__stage="RECOGIDA")
    )
    r = Q(current_version__destination_id__in=location_ids(actor, "RECEPCION")) & (
        Q(current_version__receiver=actor)
        | Q(versions__conformities__user=actor, versions__conformities__stage="RECEPCION")
    )
    roles = ["PRODUCCION", "TRANSPORTE"] if purpose == "transfers" else ["RECEPCION"]
    if not active_assignments(actor).filter(role_id__in=roles).exists():
        raise DomainError("PERMISSION_DENIED", "Sin permiso para este informe.", 403)
    return query.filter(p | t if purpose == "transfers" else r).distinct()


def transfer_metrics(actor, filters, purpose=None):
    local = ZoneInfo("America/Lima")
    start = datetime.combine(filters["date_from"], time.min, local)
    end = datetime.combine(filters["date_to"] + timedelta(days=1), time.min, local)
    events = Conformity.objects.filter(
        stage__in=["RECOGIDA", "RECEPCION"], occurred_at__gte=start, occurred_at__lt=end
    )
    if purpose == "receptions":
        events = events.filter(stage="RECEPCION")
    query = report_transfers(actor, purpose).filter(pk__in=events.values("version__transfer_id"))
    for parameter, field in [("center_id", "origin_id"), ("destination_id", "destination_id")]:
        if parameter in filters:
            query = query.filter(**{f"current_version__{field}": filters[parameter]})
    if "product_id" in filters:
        query = query.filter(current_version__lines__presentation__product_id=filters["product_id"])
    transfers = bounded(
        query.select_related("current_version__origin", "current_version__destination")
        .prefetch_related("current_version__lines__presentation__product")
        .order_by("code")
        .distinct()
    )
    ids = [row.id for row in transfers]
    physical = defaultdict(dict)
    for event in bounded(
        Conformity.objects.filter(
            version__transfer_id__in=ids, stage__in=["RECOGIDA", "RECEPCION"]
        ).select_related("version"),
        limit=20000,
    ):
        physical[event.version.transfer_id][event.stage] = event.occurred_at
    corrected = set(
        Correction.objects.filter(transfer_id__in=ids, state="APLICADA").values_list(
            "transfer_id", flat=True
        )
    )
    rows, amounts, counts = [], defaultdict(Decimal), defaultdict(int)
    for transfer in transfers:
        version = transfer.current_version
        liters = sum(
            (
                line.quantity
                for line in version.lines.all()
                if line.presentation.product.code == "LECHE"
                and (
                    "product_id" not in filters
                    or line.presentation.product_id == filters["product_id"]
                )
            ),
            Decimal(0),
        )
        dates = physical[transfer.id]
        pickup, reception = dates.get("RECOGIDA"), dates.get("RECEPCION")
        flags = {}
        for stage, instant in [("pickup", pickup), ("reception", reception)]:
            flags[stage] = instant is not None and start <= instant < end
            if flags[stage]:
                day = instant.astimezone(local).date()
                amounts[(day, stage)] += liters
                counts[(day, stage)] += 1
        rows.append(
            dict(
                transfer_id=transfer.id,
                code=transfer.code,
                version_id=version.id,
                version_number=version.number,
                origin_id=version.origin_id,
                origin_name=version.origin.name,
                destination_id=version.destination_id,
                destination_name=version.destination.name,
                state=transfer.state,
                liters=decimal(liters),
                corrected=transfer.id in corrected,
                pickup_at=pickup,
                reception_at=reception,
                pickup_in_period=flags["pickup"],
                reception_in_period=flags["reception"],
            )
        )
    days = []
    for offset in range((filters["date_to"] - filters["date_from"]).days + 1):
        day = filters["date_from"] + timedelta(days=offset)
        days.append(
            dict(
                date=day,
                picked_up_liters=decimal(amounts[(day, "pickup")]),
                received_liters=decimal(amounts[(day, "reception")]),
                picked_up_count=counts[(day, "pickup")],
                received_count=counts[(day, "reception")],
            )
        )
    return {
        **metadata(filters),
        "records": rows,
        "days": days,
        "picked_up_liters": decimal(
            sum((value for (day, stage), value in amounts.items() if stage == "pickup"), Decimal(0))
        ),
        "received_liters": decimal(
            sum(
                (value for (day, stage), value in amounts.items() if stage == "reception"),
                Decimal(0),
            )
        ),
        "picked_up_count": sum(
            value for (day, stage), value in counts.items() if stage == "pickup"
        ),
        "received_count": sum(
            value for (day, stage), value in counts.items() if stage == "reception"
        ),
    }


class TransferMetricsView(APIView):
    @extend_schema(
        parameters=[TransferQuery],
        responses={200: TransferMetrics, 403: ErrorSerializer, 422: ErrorSerializer},
    )
    @snapshot
    def get(self, request):
        query = TransferQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(transfer_metrics(request.user, query.validated_data))
