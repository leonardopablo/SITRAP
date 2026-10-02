from django.urls import path

from .milk import MilkMetricsView
from .transfers import TransferMetricsView

urlpatterns = [
    path("metrics/transfers", TransferMetricsView.as_view()),
    path("metrics/milk", MilkMetricsView.as_view()),
]
