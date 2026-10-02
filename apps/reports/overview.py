from collections import defaultdict
from decimal import Decimal

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import require_admin
from apps.catalog.models import Location
from apps.common.errors import ErrorSerializer

from .common import PeriodQuery, decimal, metadata, snapshot
from .milk import MilkMetrics, milk_metrics
from .pdf import PDF_RESPONSES, production_sections, render_pdf
from .transfer_pdf import transfer_sections
from .transfers import TransferMetrics, transfer_metrics


class CenterSummary(serializers.Serializer):
    center_id = serializers.UUIDField()
    name = serializers.CharField()
    produced_liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    picked_up_liters = serializers.DecimalField(max_digits=20, decimal_places=3)
    received_liters = serializers.DecimalField(max_digits=20, decimal_places=3)


class Overview(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    cutoff = serializers.DateTimeField()
    timezone = serializers.CharField()
    synchronized_only = serializers.BooleanField()
    centers = CenterSummary(many=True)
    production = MilkMetrics()
    transfers = TransferMetrics()


def overview(actor, filters):
    require_admin(actor)
    production = milk_metrics(actor, filters)
    transfers = transfer_metrics(actor, filters)
    totals = defaultdict(lambda: defaultdict(Decimal))
    for row in production["records"]:
        totals[row["center_id"]]["produced"] += Decimal(row["liters"])
    for row in transfers["records"]:
        values = totals[row["origin_id"]]
        if row["pickup_in_period"]:
            values["picked_up"] += Decimal(row["liters"])
        if row["reception_in_period"]:
            values["received"] += Decimal(row["liters"])
    names = dict(Location.objects.filter(id__in=totals).values_list("id", "name"))
    return {
        **metadata(filters),
        "production": production,
        "transfers": transfers,
        "centers": [
            dict(
                center_id=id,
                name=names[id],
                produced_liters=decimal(totals[id]["produced"]),
                picked_up_liters=decimal(totals[id]["picked_up"]),
                received_liters=decimal(totals[id]["received"]),
            )
            for id in sorted(totals, key=lambda id: (names[id], str(id)))
        ],
    }


class OverviewView(APIView):
    @extend_schema(
        parameters=[PeriodQuery],
        responses={200: Overview, 403: ErrorSerializer, 422: ErrorSerializer},
    )
    @snapshot
    def get(self, request):
        query = PeriodQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(overview(request.user, query.validated_data))


class OverviewPDFView(APIView):
    @extend_schema(
        parameters=[PeriodQuery],
        responses={
            (200, "application/pdf"): PDF_RESPONSES[200],
            403: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    @snapshot
    def get(self, request):
        query = PeriodQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = overview(request.user, query.validated_data)
        sections = [
            {
                "title": "Resumen por centro de origen",
                "text": "Medidas separadas según fecha de producción y etapas físicas. No equivalen a stock, ventas ni rentabilidad.",
                "headers": ["Centro", "Producido (L)", "Recogido (L)", "Recibido (L)"],
                "rows": [
                    [
                        row["name"],
                        row["produced_liters"],
                        row["picked_up_liters"],
                        row["received_liters"],
                    ]
                    for row in data["centers"]
                ],
            }
        ]
        sections += production_sections(data["production"])
        sections += transfer_sections(data["transfers"])
        return render_pdf("Resumen administrativo", data, query.validated_data, sections, "resumen")
