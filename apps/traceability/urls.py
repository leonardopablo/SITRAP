from django.urls import path

from apps.traceability.views import (
    CancelTransferView,
    LotDetailView,
    LotsView,
    PickupTransferView,
    ReceiveTransferView,
    ReviseTransferView,
    SendTransferView,
    TimelineView,
    TransferDetailView,
    TransfersView,
)

from .correction_views import (
    AcceptCorrectionView,
    CorrectionDetailView,
    CorrectionsView,
    CreateCorrectionView,
)

urlpatterns = [
    path("corrections/<uuid:pk>/accept", AcceptCorrectionView.as_view()),
    path("transfers/<uuid:pk>/corrections", CreateCorrectionView.as_view()),
    path("corrections", CorrectionsView.as_view()),
    path("corrections/<uuid:pk>", CorrectionDetailView.as_view()),
    path("transfers/<uuid:pk>/receive", ReceiveTransferView.as_view()),
    path("transfers/<uuid:pk>/pickup", PickupTransferView.as_view()),
    path("transfers/<uuid:pk>/revise", ReviseTransferView.as_view()),
    path("transfers/<uuid:pk>/cancel", CancelTransferView.as_view()),
    path("transfers/<uuid:pk>/send", SendTransferView.as_view()),
    path("lots", LotsView.as_view()),
    path("lots/<uuid:pk>", LotDetailView.as_view()),
    path("transfers", TransfersView.as_view()),
    path("transfers/<uuid:pk>", TransferDetailView.as_view()),
    path("transfers/<uuid:pk>/timeline", TimelineView.as_view()),
]
