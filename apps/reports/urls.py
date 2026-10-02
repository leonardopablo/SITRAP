from django.urls import path

from .milk import MilkMetricsView
from .pdf import ProductionPDFView
from .transfers import TransferMetricsView

urlpatterns = [
    path("reports/production.pdf", ProductionPDFView.as_view()),
    path("metrics/transfers", TransferMetricsView.as_view()),
    path("metrics/milk", MilkMetricsView.as_view()),
]
