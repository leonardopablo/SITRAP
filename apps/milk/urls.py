from django.urls import path

from apps.milk.views import MilkingConfirmView, MilkingDetailView, MilkingsView

urlpatterns = [
    path("milkings", MilkingsView.as_view()),
    path("milkings/<uuid:pk>", MilkingDetailView.as_view()),
]

urlpatterns += [path("milkings/<uuid:pk>/confirm", MilkingConfirmView.as_view())]
