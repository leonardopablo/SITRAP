from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from apps.accounts.admin_api import (
    AssignmentDetailView,
    AssignmentsView,
    ResetPasswordView,
    UserDetailView,
    UsersView,
)
from apps.accounts.options import AssignmentOptionsView
from apps.sync.batch_views import SyncEventsView
from apps.sync.snapshot_views import BootstrapView, ChangesView
from apps.sync.views import CurrentDeviceView, DeviceView
from config.views import HealthView

urlpatterns = [
    path("api/v1/sync/events", SyncEventsView.as_view()),
    path("api/v1/sync/bootstrap", BootstrapView.as_view()),
    path("api/v1/sync/changes", ChangesView.as_view()),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.traceability.urls")),
    path("api/v1/", include("apps.milk.urls")),
    path("api/v1/assignment-options", AssignmentOptionsView.as_view()),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/users", UsersView.as_view()),
    path("api/v1/users/<uuid:pk>", UserDetailView.as_view()),
    path("api/v1/users/<uuid:pk>/reset-password", ResetPasswordView.as_view()),
    path("api/v1/role-assignments", AssignmentsView.as_view()),
    path("api/v1/role-assignments/<uuid:pk>", AssignmentDetailView.as_view()),
    path("api/v1/devices", DeviceView.as_view()),
    path("api/v1/devices/current", CurrentDeviceView.as_view()),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/health", HealthView.as_view(), name="health"),
    path("api/v1/schema", SpectacularAPIView.as_view(), name="schema"),
]
