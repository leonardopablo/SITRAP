from django.urls import path

from . import sales_views as sales
from . import views

urlpatterns = [
    path("sales/modules", sales.ModulesView.as_view()),
    path("sales/availability", sales.AvailabilityView.as_view()),
    path("sales/options", sales.SalesOptionsView.as_view()),
    path("sales/orders", sales.OrdersView.as_view()),
    path("sales/orders/<uuid:pk>", sales.OrderDetailView.as_view()),
    path("sales/orders/<uuid:pk>/candidates", sales.CandidatesView.as_view()),
    path("sales/orders/<uuid:pk>/pin", sales.PinGenerateView.as_view()),
    path("sales/orders/<uuid:pk>/deliver-direct", sales.PinDeliveryView.as_view()),
    path("sales/vouchers", sales.VouchersView.as_view()),
    path("sales/vouchers/<uuid:pk>", sales.VoucherDetailView.as_view()),
    path("sales/commands", sales.CommercialCommandsView.as_view()),
    path("config", views.ConfigView.as_view()),
    path("sheds", views.ShedsView.as_view()),
    path("pens", views.PensView.as_view()),
    path("pens/<uuid:pk>", views.PenDetailView.as_view()),
    path("balances", views.PensView.as_view()),
    path("destinations", views.DestinationsView.as_view()),
    path("kardex", views.KardexView.as_view()),
    path("history", views.KardexView.as_view()),
    path("transfers", views.TransfersView.as_view()),
    path("counts", views.CountsView.as_view()),
    path("daily-reports", views.ReportsView.as_view()),
    path("dashboard", views.DashboardView.as_view()),
    path("alerts", views.AlertsView.as_view()),
    path("commands", views.CommandsView.as_view()),
]
