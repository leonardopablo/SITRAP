from django.urls import path

from .views import NotificationsView, ReadNotificationView

urlpatterns = [
    path("notifications", NotificationsView.as_view()),
    path("notifications/<uuid:pk>/read", ReadNotificationView.as_view()),
]
