from django.conf import settings
from django.core.checks import Error, register

from .push_config import private_key


@register()
def check_vapid(app_configs, **kwargs):
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
