import hashlib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import LoginBucket, User
from apps.accounts.serializers import (
    CSRFSerializer,
    LoginSerializer,
    MeSerializer,
    PasswordSerializer,
)
from apps.common.errors import DomainError, ErrorSerializer


def me_data(user, request):
    data = MeSerializer(user).data
    data["session_expires_at"] = request.session.get_expiry_date().isoformat()
    return data


def consume_login_budget(request, username):
    # Never trust a caller-supplied X-Forwarded-For. Configure trusted proxy handling separately.
    bucket = int(timezone.now().timestamp()) // settings.LOGIN_WINDOW_SECONDS
    keys = [
        ("user:" + username.casefold(), settings.LOGIN_USER_LIMIT),
        ("ip:" + request.META.get("REMOTE_ADDR", ""), settings.LOGIN_IP_LIMIT),
    ]
    exhausted = False
    with transaction.atomic():
        for value, limit in sorted(keys):
            key = hashlib.sha256(f"{bucket}:{value}".encode()).hexdigest()
            item, _ = LoginBucket.objects.get_or_create(key=key)
            item = LoginBucket.objects.select_for_update().get(pk=item.pk)
            if item.attempts >= limit:
                exhausted = True
            else:
                item.attempts += 1
                item.save(update_fields=["attempts"])
    if exhausted:
        raise DomainError("RATE_LIMITED", "Espere antes de volver a ingresar.", 429, retryable=True)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CSRFView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses=CSRFSerializer, auth=[])
    def get(self, request):
        return Response({"csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: MeSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            422: ErrorSerializer,
            429: ErrorSerializer,
        },
        auth=[],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consume_login_budget(request, serializer.validated_data["username"])
        user = authenticate(request, **serializer.validated_data)
        if user is None:
            raise DomainError("INVALID_CREDENTIALS", "Usuario o contraseña incorrectos.", 401)
        login(request, user)
        request.session.set_expiry(timezone.now() + timedelta(seconds=settings.SESSION_COOKIE_AGE))
        return Response(me_data(user, request))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer, 401: ErrorSerializer})
    def get(self, request):
        return Response(me_data(request.user, request))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None, 401: ErrorSerializer, 403: ErrorSerializer})
    def post(self, request):
        logout(request)
        return Response(status=204)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PasswordSerializer,
        responses={
            200: MeSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = PasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if not user.check_password(serializer.validated_data["old_password"]):
                raise DomainError(
                    "VALIDATION_ERROR",
                    "La contraseña actual no coincide.",
                    422,
                    {"old_password": ["No coincide."]},
                )
            validate_password(serializer.validated_data["new_password"], user=user)
            user.set_password(serializer.validated_data["new_password"])
            user.password_change_required = False
            user.save(update_fields=["password", "password_change_required"])
            # Session auth hash invalidates all other sessions on their next request.
            update_session_auth_hash(request, user)
            request.user = user
        return Response(me_data(user, request))
