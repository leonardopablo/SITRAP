from pathlib import Path
from zoneinfo import ZoneInfo

from django.http import HttpResponse
from django.template import Context, Engine
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.views import APIView

from apps.catalog.models import Location, Turn
from apps.common.errors import ErrorSerializer

from .common import snapshot
from .milk import MilkQuery, milk_metrics

ENGINE = Engine(dirs=[str(Path(__file__).parent / "templates")], autoescape=True)


def deny_fetch(url, *args, **kwargs):
    raise ValueError("External resources are disabled for reports.")


def render_pdf(title, data, filters, sections, filename):
    from weasyprint import HTML

    context = {
        "title": title,
        "data": data,
        "filters": {k: str(v) for k, v in filters.items()},
        "cutoff": data["cutoff"].astimezone(ZoneInfo("America/Lima")).isoformat(),
        "sections": sections,
    }
    html = ENGINE.get_template("report.html").render(Context(context, use_l10n=False))
    content = HTML(string=html, url_fetcher=deny_fetch).write_pdf()
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def production_sections(data):
    animals = {str(row["animal_id"]): row for row in data["animals"]}
    centers = dict(
        Location.objects.filter(id__in={row["center_id"] for row in data["records"]}).values_list(
            "id", "name"
        )
    )
    turns = dict(
        Turn.objects.filter(id__in={row["turn_id"] for row in data["records"]}).values_list(
            "id", "name"
        )
    )
    return [
        {
            "title": "Producción confirmada",
            "text": f"Total: {data['liters']} L. Días con registro: {data['recorded_days']}. Promedio por día registrado: {data['average_per_recorded_day'] or 'Sin registro'} L.",
            "headers": [
                "Vaca",
                "Litros",
                "Días con registro",
                "Días en centro",
                "Días sin registro",
                "Promedio L/día",
            ],
            "rows": [
                [
                    f"{row['code']} {row['name']}",
                    row["liters"],
                    row["recorded_days"],
                    row["days_present"],
                    row["days_without_record"],
                    row["average_per_recorded_day"]
                    if row["average_per_recorded_day"] is not None
                    else "Sin registro",
                ]
                for row in data["animals"]
            ],
        },
        {
            "title": "Detalle vigente por fecha y turno",
            "text": "Cero es un registro. Ausencia no es cero. Cobertura basada en estancias, sin inferir lactancia. Borradores y anulaciones excluidos.",
            "headers": ["Fecha", "Centro", "Turno", "Vaca", "Litros"],
            "rows": [
                [
                    row["date"].isoformat(),
                    centers[row["center_id"]],
                    turns[row["turn_id"]],
                    animals[str(row["animal_id"])]["code"],
                    row["liters"],
                ]
                for row in data["records"]
            ],
        },
    ]


PDF_RESPONSES = {
    200: OpenApiResponse(
        response=OpenApiTypes.BINARY,
        description="PDF con datos sincronizados al corte del servidor.",
    ),
    403: ErrorSerializer,
    422: ErrorSerializer,
}


class ProductionPDFView(APIView):
    @extend_schema(
        parameters=[MilkQuery],
        responses={
            (200, "application/pdf"): PDF_RESPONSES[200],
            403: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    @snapshot
    def get(self, request):
        query = MilkQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = milk_metrics(request.user, query.validated_data)
        return render_pdf(
            "Informe de producción",
            data,
            query.validated_data,
            production_sections(data),
            "produccion",
        )
