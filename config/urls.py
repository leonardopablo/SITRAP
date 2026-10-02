from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from apps.sync.views import CurrentDeviceView, DeviceView
from config.views import HealthView

urlpatterns = [
    path("api/v1/devices", DeviceView.as_view()),
    path("api/v1/devices/current", CurrentDeviceView.as_view()),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/health", HealthView.as_view(), name="health"),
    path("api/v1/schema", SpectacularAPIView.as_view(), name="schema"),
]
