from django.db import connection

from apps.common.errors import DomainError

from .models import Notification

EVENT_TYPES = {
    "PICKUP_REQUESTED",
    "PICKUP_REQUEST_UPDATED",
    "TRANSFER_CANCELLED",
    "RECEPTION_PENDING",
    "RECEIVER_REASSIGNED",
    "RECEPTION_CONFIRMED",
    "CORRECTION_REQUESTED",
    "CORRECTION_PROGRESS",
    "CORRECTION_APPLIED",
    "CORRECTION_REJECTED",
    "CORRECTION_WITHDRAWN",
}


def notify(
    *,
    recipients,
    type,
    source_event_id,
    entity_type,
    entity_id,
    version_id=None,
    title="Actualización de SITRAP",
    text="Consulte el estado actual en la aplicación.",
):
    if not connection.in_atomic_block:
        raise RuntimeError("Notifications must share the business transaction.")
    if type not in EVENT_TYPES:
        raise ValueError("Unknown notification type")
    content = dict(
        entity_type=entity_type, entity_id=entity_id, version_id=version_id, title=title, text=text
    )
    result = []
    for recipient_id in sorted(set(recipients), key=str):
        notification, created = Notification.objects.get_or_create(
            recipient_id=recipient_id, source_event_id=source_event_id, type=type, defaults=content
        )
        if not created and any(
            str(getattr(notification, key)) != str(value) for key, value in content.items()
        ):
            raise DomainError("IDEMPOTENCY_CONFLICT", "El aviso ya existe con otro contenido.")
        if created:
            from .outbox import enqueue

            enqueue(notification)
        result.append(notification)
    return result
