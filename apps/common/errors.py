from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import JsonResponse
from rest_framework import exceptions, serializers
from rest_framework.response import Response


class DomainError(exceptions.APIException):
    def __init__(self, code, message, status=409, field_errors=None, retryable=False):
        self.status_code = status
        self.detail = {
            "code": code,
            "message": message,
            "field_errors": field_errors or {},
            "retryable": retryable,
        }


class ErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    field_errors = serializers.DictField()
    retryable = serializers.BooleanField()


def error_handler(exc, context):
    from rest_framework.views import exception_handler

    if isinstance(exc, DomainError):
        return Response(exc.detail, status=exc.status_code)
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(getattr(exc, "message_dict", exc.messages))
    response = exception_handler(exc, context)
    if response is None:
        return None
    status = response.status_code
    code = {
        400: "VALIDATION_ERROR",
        401: "SESSION_EXPIRED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "RATE_LIMITED",
    }.get(status, "REQUEST_ERROR")
    if status == 400:
        response.status_code = 422
    response.data = {
        "code": code,
        "message": "Revise los campos."
        if status == 400
        else str(getattr(exc, "detail", "Solicitud no válida.")),
        "field_errors": response.data if status == 400 else {},
        "retryable": status in (401, 429),
    }
    return response


def csrf_failure(request, reason=""):
    return JsonResponse(
        {
            "code": "CSRF_FAILED",
            "message": "Renueve CSRF e intente nuevamente.",
            "field_errors": {},
            "retryable": True,
        },
        status=403,
    )
