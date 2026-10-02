from django.db.models import Q

from apps.accounts.access import is_admin, location_ids
from apps.traceability.models import Lot, Transfer, TransferLine


def scoped_transfers(actor):
    query = Transfer.objects.all()
    if is_admin(actor):
        return query
    p = Q(current_version__origin_id__in=location_ids(actor, "PRODUCCION"))
    t = Q(current_version__origin_id__in=location_ids(actor, "TRANSPORTE")) & (
        Q(current_version__driver=actor)
        | Q(versions__conformities__user=actor, versions__conformities__stage="RECOGIDA")
    )
    r = Q(current_version__destination_id__in=location_ids(actor, "RECEPCION")) & (
        Q(current_version__receiver=actor)
        | Q(versions__conformities__user=actor, versions__conformities__stage="RECEPCION")
    )
    return query.filter(p | (~Q(state="BORRADOR") & (t | r))).distinct()


def scoped_lots(actor):
    query = Lot.objects.select_related("production__current_version", "production__milking")
    if is_admin(actor):
        return query
    linked = TransferLine.objects.filter(version__transfer__in=scoped_transfers(actor)).values(
        "lot_id"
    )
    return query.filter(
        Q(production__center_id__in=location_ids(actor, "PRODUCCION")) | Q(id__in=linked)
    )


def lot_data(lot):
    production = lot.production
    return {
        "id": lot.id,
        "code": lot.code,
        "production_id": production.id,
        "center_id": production.center_id,
        "product_id": production.product_id,
        "responsible_id": production.responsible_id,
        "date": production.milking.date,
        "turn_id": production.milking.turn_id,
        "quantity": production.current_version.quantity,
        "production_state": production.state,
        "created_at": lot.created_at,
    }


def version_data(version):
    if version is None:
        return None
    return {
        "id": version.id,
        "number": version.number,
        "origin_id": version.origin_id,
        "destination_id": version.destination_id,
        "emitter_id": version.emitter_id,
        "driver_id": version.driver_id,
        "receiver_id": version.receiver_id,
        "state": version.state,
        "reason": version.reason,
        "published_at": version.published_at,
        "lines": list(
            version.lines.order_by("id").values(
                "id",
                "lot_id",
                "presentation_id",
                "units",
                "content_base_snapshot",
                "quantity",
            )
        ),
    }


def transfer_data(transfer, actor):
    return {
        "id": transfer.id,
        "code": transfer.code,
        "creator_id": transfer.creator_id,
        "state": transfer.state,
        "lock_version": transfer.lock_version,
        "version_id": transfer.current_version_id,
        "pending_correction_id": transfer.corrections.filter(state="PENDIENTE")
        .values_list("id", flat=True)
        .first(),
        "current_version": version_data(transfer.current_version),
        "versions": [version_data(version) for version in transfer.versions.order_by("number")],
        "capabilities": transfer_capabilities(transfer, actor),
    }


def timeline(transfer):
    events = []
    for version in transfer.versions.order_by("number"):
        if version.published_at:
            events.append(
                {
                    "type": "VERSION_PUBLISHED",
                    "at": version.published_at,
                    "version_id": version.id,
                    "actor_id": version.emitter_id,
                }
            )
        for conformity in version.conformities.all():
            events.append(
                {
                    "type": conformity.stage,
                    "at": conformity.occurred_at,
                    "version_id": version.id,
                    "actor_id": conformity.user_id,
                    "registered_at": conformity.registered_at,
                }
            )
    for correction in transfer.corrections.all():
        events.append(
            {
                "type": "CORRECTION_CREATED",
                "at": correction.created_at,
                "version_id": correction.proposed_version_id,
                "actor_id": correction.requester_id,
            }
        )
    return sorted(events, key=lambda item: (item["at"], str(item["version_id"]), item["type"]))


def transfer_capabilities(transfer, actor):
    result = []
    version = transfer.current_version
    if version.origin_id in location_ids(actor, "PRODUCCION"):
        if transfer.state == "BORRADOR":
            result += ["update", "send", "cancel"]
        if transfer.state == "PENDIENTE_RECOGIDA":
            result += ["revise", "cancel"]
    if (
        transfer.state == "PENDIENTE_RECOGIDA"
        and version.driver_id == actor.id
        and version.origin_id in location_ids(actor, "TRANSPORTE")
    ):
        result.append("pickup")
    if (
        transfer.state == "EN_CAMINO"
        and version.receiver_id == actor.id
        and version.destination_id in location_ids(actor, "RECEPCION")
    ):
        if not transfer.corrections.filter(state="PENDIENTE").exists():
            result.append("receive")
    if (
        transfer.state in ["EN_CAMINO", "RECIBIDO"]
        and version.origin_id in location_ids(actor, "PRODUCCION")
        and not transfer.corrections.filter(state="PENDIENTE").exists()
    ):
        result.append("request_correction")
    return result
