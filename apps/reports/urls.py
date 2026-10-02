from django.urls import path

from .milk import MilkMetricsView

urlpatterns = [path("metrics/milk", MilkMetricsView.as_view())]
