from apps.accounts.access import active_assignments
from apps.accounts.models import User
from apps.notifications.services import notify

from .access import sheds_for
from .services import recipients


def workers(center_id):
    return [
        user.id for user in User.objects.filter(is_active=True)
        if sheds_for(user, operational=True).filter(center_id=center_id).exists()
        and active_assignments(user).filter(role_id="GALPONERO", location_id=center_id).exists()
    ]


def sale_notice(order, kind, source_event):
    if kind == "SALE_REQUESTED":
        targets = workers(order.center_id)
    elif kind == "SALE_PAID":
        targets = workers(order.center_id)
        if order.mode == "PUNTO" and order.driver_id:
            targets.append(order.driver_id)
    elif kind == "SALE_DRIVER":
        targets = [order.driver_id] if order.driver_id else []
    else:
        targets = recipients()
    notify(
        recipients=targets, type=kind, source_event_id=source_event,
        entity_type="cuy_sale", entity_id=order.id,
        title="Cuyes: actualización de venta",
        text="Consulte la orden y sus acciones pendientes en la aplicación.",
    )
