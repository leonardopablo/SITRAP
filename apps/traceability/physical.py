from rest_framework import serializers

from apps.accounts.access import require_assigned
from apps.common.errors import DomainError
from apps.notifications.services import notify
from apps.sync.serializers import EnvelopeSerializer

from .lifecycle import VersionPayload, ensure_document, finish, locked_transfer, sign
from .models import Transfer
from .reads import transfer_data


class TransferPickupCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["TRANSFER_PICKUP"], default="TRANSFER_PICKUP")
    expected_version = serializers.IntegerField(min_value=1)
    payload = VersionPayload()


def authorize_physical(actor, command):
    transfer = (
        Transfer.objects.filter(pk=command["entity_id"]).select_related("current_version").first()
    )
    if transfer is None:
        raise DomainError("NOT_FOUND", "Entrega no disponible.", 404)
    version = transfer.current_version
    if command["type"] == "TRANSFER_RECEIVE":
        require_assigned(actor, "RECEPCION", version.destination_id, version.receiver_id)
    else:
        require_assigned(actor, "TRANSPORTE", version.origin_id, version.driver_id)


def pickup(actor, command, operation):
    transfer = locked_transfer(command)
    version = transfer.current_version
    require_assigned(actor, "TRANSPORTE", version.origin_id, version.driver_id)
    if transfer.state != "PENDIENTE_RECOGIDA":
        raise DomainError("INVALID_STATE", "La entrega no está pendiente de recogida.")
    ensure_document(transfer, command["payload"]["version_id"])
    before = transfer_data(transfer, actor)
    sign(transfer, actor, operation, "RECOGIDA")
    transfer.state = "EN_CAMINO"
    notify(
        recipients=[version.receiver_id],
        type="RECEPTION_PENDING",
        source_event_id=operation.event_id,
        entity_type="transfer",
        entity_id=transfer.id,
        version_id=version.id,
    )
    return finish(transfer, actor, operation, before)


def physical_commands():
    return {
        "TRANSFER_PICKUP": (TransferPickupCommand, pickup, authorize_physical),
        "TRANSFER_RECEIVE": (TransferReceiveCommand, receive, authorize_physical),
    }


class TransferReceiveCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["TRANSFER_RECEIVE"], default="TRANSFER_RECEIVE")
    expected_version = serializers.IntegerField(min_value=1)
    payload = VersionPayload()


def receive(actor, command, operation):
    transfer = locked_transfer(command)
    version = transfer.current_version
    require_assigned(actor, "RECEPCION", version.destination_id, version.receiver_id)
    if transfer.state != "EN_CAMINO":
        raise DomainError("INVALID_STATE", "La entrega no está en camino.")
    # B23 adds the pending-correction guard before correction creation is exposed.
    ensure_document(transfer, command["payload"]["version_id"])
    before = transfer_data(transfer, actor)
    sign(transfer, actor, operation, "RECEPCION")
    transfer.state = "RECIBIDO"
    notify(
        recipients=[version.emitter_id, version.driver_id],
        type="RECEPTION_CONFIRMED",
        source_event_id=operation.event_id,
        entity_type="transfer",
        entity_id=transfer.id,
        version_id=version.id,
    )
    return finish(transfer, actor, operation, before)
