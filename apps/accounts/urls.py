from django.urls import path

from apps.accounts.views import ChangePasswordView, CSRFView, LoginView, LogoutView, MeView

urlpatterns = [
    path("csrf", CSRFView.as_view()),
    path("login", LoginView.as_view()),
    path("me", MeView.as_view()),
    path("logout", LogoutView.as_view()),
    path("change-password", ChangePasswordView.as_view()),
]
