from django.conf import settings
from django.core.checks import Error, register

from .push_config import private_key


@register()
def check_vapid(app_configs, **kwargs):
    if (
        settings.PUSH_HTTP_TIMEOUT_SECONDS < 1
        or settings.PUSH_LEASE_SECONDS <= settings.PUSH_HTTP_TIMEOUT_SECONDS + 5
        or settings.PUSH_MAX_ATTEMPTS < 1
        or settings.PUSH_RETRY_BASE_SECONDS < 1
        or settings.PUSH_POLL_SECONDS < 1
    ):
        return [Error("Revise tiempos, lease y límite de intentos push.", id="notifications.E002")]
    if settings.PUSH_ENABLED:
        try:
            private_key()
        except ValueError:
            return [
                Error(
                    "PUSH_ENABLED requiere claves VAPID P-256 coincidentes y VAPID_SUBJECT.",
                    id="notifications.E001",
                )
            ]
    return []
