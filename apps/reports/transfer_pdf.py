from zoneinfo import ZoneInfo

from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.common.errors import ErrorSerializer

from .common import snapshot
from .pdf import PDF_RESPONSES, render_pdf
from .transfers import TransferQuery, transfer_metrics


def local_time(value):
    return (
        value.astimezone(ZoneInfo("America/Lima")).strftime("%Y-%m-%d %H:%M")
        if value
        else "Pendiente"
    )


def transfer_sections(data, purpose="transfers"):
    summary = f"Recibido: {data['received_liters']} L en {data['received_count']} entregas."
    if purpose != "receptions":
        summary = (
            f"Recogido: {data['picked_up_liters']} L en {data['picked_up_count']} entregas. "
            + summary
        )
    return [
        {
            "title": "Entregas del período",
            "text": summary + " Medidas separadas; no sumarlas como producción.",
            "headers": [
                "Documento",
                "Ruta",
                "Recogida (Lima)",
                "Recepción (Lima)",
                "Litros vigentes",
                "Estado",
            ],
            "rows": [
                [
                    f"{row['code']} / v{row['version_number']}",
                    f"{row['origin_name']} → {row['destination_name']}",
                    local_time(row["pickup_at"]),
                    local_time(row["reception_at"]),
                    row["liters"] + (" (corregida)" if row["corrected"] else ""),
                    row["state"],
                ]
                for row in data["records"]
            ],
        }
    ]


class TransfersPDFView(APIView):
    purpose = "transfers"

    @extend_schema(
        parameters=[TransferQuery],
        responses={
            (200, "application/pdf"): PDF_RESPONSES[200],
            403: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    @snapshot
    def get(self, request):
        query = TransferQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = transfer_metrics(request.user, query.validated_data, self.purpose)
        title = (
            "Informe de recepciones" if self.purpose == "receptions" else "Informe de transporte"
        )
        return render_pdf(
            title, data, query.validated_data, transfer_sections(data, self.purpose), self.purpose
        )


class ReceptionsPDFView(TransfersPDFView):
    purpose = "receptions"
