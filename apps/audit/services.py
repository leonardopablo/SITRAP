import json
from decimal import Decimal

from django.db import connection, transaction

from apps.audit.models import AuditEntry
from apps.sync.services import json_default

SECRET_KEYS = {
    "password",
    "old_password",
    "new_password",
    "temporary_password",
    "p256dh",
    "auth",
    "endpoint",
    "session_key",
    "csrf_token",
    "secret_key",
    "private_key",
}


def clean(value):
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in SECRET_KEYS else clean(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


def snapshot(value):
    return json.loads(json.dumps(clean(value), default=json_default))


def record(
    actor, entity_type, entity_id, action, *, before=None, after=None, reason="", operation=None
):
    if not connection.in_atomic_block:
        raise RuntimeError("Audit writes must share the business transaction.")
    return AuditEntry.objects.create(
        actor=actor,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=snapshot(before or {}),
        after=snapshot(after or {}),
        reason=reason,
        operation=operation,
    )


@transaction.atomic
def atomic_change(actor, entity_type, entity_id, action, change, *, before=None, reason=""):
    result = change()
    record(actor, entity_type, entity_id, action, before=before, after=result, reason=reason)
    return result
