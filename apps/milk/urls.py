from django.urls import path

from apps.milk.views import MilkingDetailView, MilkingsView

urlpatterns = [
    path("milkings", MilkingsView.as_view()),
    path("milkings/<uuid:pk>", MilkingDetailView.as_view()),
]
