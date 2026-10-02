from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from apps.common.errors import DomainError


class SessionAuth(SessionAuthentication):
    def authenticate_header(self, request):
        return "Session"

    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except PermissionDenied:
            raise DomainError(
                "CSRF_FAILED", "Renueve CSRF e intente nuevamente.", 403, retryable=True
            )


class ReadyAccount(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.password_change_required:
            raise DomainError("PASSWORD_CHANGE_REQUIRED", "Cambie su contraseña temporal.", 403)
        return True
