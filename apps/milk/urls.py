from django.urls import path

from apps.milk.views import MilkingConfirmView, MilkingDetailView, MilkingsView

from .views import MilkingRectifyView, MilkingVoidView

urlpatterns = [
    path("milkings/<uuid:pk>/rectify", MilkingRectifyView.as_view()),
    path("milkings/<uuid:pk>/void", MilkingVoidView.as_view()),
    path("milkings", MilkingsView.as_view()),
    path("milkings/<uuid:pk>", MilkingDetailView.as_view()),
]

urlpatterns += [path("milkings/<uuid:pk>/confirm", MilkingConfirmView.as_view())]
