from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from config.views import HealthView

urlpatterns = [
    path("api/v1/health", HealthView.as_view(), name="health"),
    path("api/v1/schema", SpectacularAPIView.as_view(), name="schema"),
]
