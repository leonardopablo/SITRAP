from django.urls import path

from apps.traceability.views import (
    LotDetailView,
    LotsView,
    TimelineView,
    TransferDetailView,
    TransfersView,
)

urlpatterns = [
    path("lots", LotsView.as_view()),
    path("lots/<uuid:pk>", LotDetailView.as_view()),
    path("transfers", TransfersView.as_view()),
    path("transfers/<uuid:pk>", TransferDetailView.as_view()),
    path("transfers/<uuid:pk>/timeline", TimelineView.as_view()),
]
