import hashlib
import json

from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import require_admin, require_role
from apps.accounts.models import User
from apps.audit.services import record, snapshot
from apps.common.errors import DomainError, ErrorSerializer
from apps.common.serializers import StrictSerializer
from apps.common.services import check_version
from apps.notifications.services import notify
from apps.sync.services import ensure_actor

from .commands import lock_context
from .models import Conformity, ReceiverReassignment
from .reads import transfer_data
from .revision import clone_document
from .serializers import TransferSerializer


class ReceiverReassignmentSerializer(StrictSerializer):
    id = serializers.UUIDField(help_text="UUID estable de esta acción online.")
    expected_version = serializers.IntegerField(min_value=1)
    version_id = serializers.UUIDField()
    line_id = serializers.UUIDField()
    receiver_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=2000)


@transaction.atomic
def reassign(actor, transfer_id, data):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    ensure_actor(actor)
    require_admin(actor)
    fingerprint = hashlib.sha256(
        json.dumps(snapshot({"transfer_id": transfer_id, **data}), sort_keys=True).encode()
    ).hexdigest()
    previous = ReceiverReassignment.objects.filter(pk=data["id"]).first()
    if previous:
        if previous.actor_id != actor.id or previous.payload_hash != fingerprint:
            raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de reasignación ya utilizado.")
        return previous.response
    _, transfer = lock_context(transfer_id, None)
    if transfer is None:
        raise DomainError("NOT_FOUND", "Entrega no disponible.", 404)
    check_version(transfer, data["expected_version"])
    if (
        transfer.state != "EN_CAMINO"
        or Conformity.objects.filter(version__transfer=transfer, stage="RECEPCION").exists()
    ):
        raise DomainError("INVALID_STATE", "Solo se reasigna antes de la recepción.")
    if transfer.corrections.exists():
        raise DomainError("INVALID_STATE", "Hay correcciones históricas; no se permite reasignar.")
    original = transfer.current_version
    receiver = User.objects.filter(pk=data["receiver_id"], is_active=True).first()
    if receiver is None:
        raise DomainError("VALIDATION_ERROR", "Receptor no disponible.", 422)
    require_role(receiver, "RECEPCION", original.destination_id)
    if receiver.id in [original.driver_id, original.receiver_id]:
        raise DomainError("VALIDATION_ERROR", "Elija otro receptor distinto del conductor.", 422)
    before = transfer_data(transfer, actor)
    try:
        with transaction.atomic():
            version = clone_document(
                original,
                version_id=data["version_id"],
                line_id=data["line_id"],
                units=original.lines.get().units,
                reason=data["reason"],
                emitter=original.emitter,
                receiver_id=receiver.id,
            )
            original.state = "SUPERADA"
            original.save(update_fields=["state"])
            version.state, version.published_at = "PUBLICADA", timezone.now()
            version.save(update_fields=["state", "published_at"])
            transfer.current_version = version
            transfer.lock_version += 1
            transfer.save()
            result = TransferSerializer(transfer_data(transfer, actor)).data
            record(
                actor,
                "transfer",
                transfer.id,
                "REASSIGN_RECEIVER",
                before=before,
                after=result,
                reason=data["reason"],
            )
            notify(
                recipients=[
                    receiver.id,
                    original.receiver_id,
                    original.driver_id,
                    original.emitter_id,
                ],
                type="RECEIVER_REASSIGNED",
                source_event_id=data["id"],
                entity_type="transfer",
                entity_id=transfer.id,
                version_id=version.id,
            )
            ReceiverReassignment.objects.create(
                id=data["id"],
                actor=actor,
                transfer=transfer,
                payload_hash=fingerprint,
                response=result,
            )
    except IntegrityError:
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de reasignación o documento ya utilizado.")
    return result


class ReassignReceiverView(APIView):
    @extend_schema(
        request=ReceiverReassignmentSerializer,
        responses={
            200: TransferSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            409: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def post(self, request, pk):
        serializer = ReceiverReassignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(reassign(request.user, pk, serializer.validated_data))
