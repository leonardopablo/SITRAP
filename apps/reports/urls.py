from django.urls import path

from .milk import MilkMetricsView
from .pdf import ProductionPDFView
from .transfer_pdf import ReceptionsPDFView, TransfersPDFView
from .transfers import TransferMetricsView

urlpatterns = [
    path("reports/transfers.pdf", TransfersPDFView.as_view()),
    path("reports/receptions.pdf", ReceptionsPDFView.as_view()),
    path("reports/production.pdf", ProductionPDFView.as_view()),
    path("metrics/transfers", TransferMetricsView.as_view()),
    path("metrics/milk", MilkMetricsView.as_view()),
]
