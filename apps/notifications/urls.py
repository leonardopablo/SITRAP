from django.urls import path

from .push_views import PushConfigView, PushSubscriptionDetailView, PushSubscriptionsView
from .views import NotificationsView, ReadNotificationView

urlpatterns = [
    path("push/config", PushConfigView.as_view()),
    path("push/subscriptions", PushSubscriptionsView.as_view()),
    path("push/subscriptions/<uuid:pk>", PushSubscriptionDetailView.as_view()),
    path("notifications", NotificationsView.as_view()),
    path("notifications/<uuid:pk>/read", ReadNotificationView.as_view()),
]
