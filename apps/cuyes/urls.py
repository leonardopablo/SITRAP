from django.urls import path

from . import views

urlpatterns = [
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
