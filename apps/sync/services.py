import hashlib
import json
from datetime import date, datetime
from datetime import timezone as dt_timezone
from decimal import Decimal
from uuid import UUID

from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.common.errors import DomainError
from apps.sync.models import Device, SyncDependency, SyncOperation
from apps.sync.serializers import EnvelopeSerializer


def json_default(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(dt_timezone.utc).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def normalize(envelope):
    serializer = EnvelopeSerializer(data=envelope)
    serializer.is_valid(raise_exception=True)
    normalized = json.loads(json.dumps(serializer.validated_data, default=json_default))
    normalized["depends_on"].sort()
    normalized.setdefault("expected_version", None)
    canonical = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return normalized, hashlib.sha256(canonical.encode()).hexdigest()


def ensure_actor(actor):
    if not actor.is_active:
        raise DomainError("SESSION_EXPIRED", "La cuenta ya no está activa.", 401, retryable=True)
    if actor.password_change_required:
        raise DomainError("PASSWORD_CHANGE_REQUIRED", "Cambie su contraseña temporal.", 403)


def owned_device(actor, device_id, *, lock=False):
    queryset = Device.objects.select_for_update() if lock else Device.objects
    device = queryset.filter(pk=device_id, user=actor, active=True).first()
    if device is None:
        raise DomainError("PERMISSION_DENIED", "Dispositivo no autorizado.", 403)
    return device


@transaction.atomic
def register_device(actor, data):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    ensure_actor(actor)
    try:
        with transaction.atomic():
            device, _ = Device.objects.get_or_create(
                id=data["id"], defaults={"user": actor, "name": data["name"]}
            )
    except IntegrityError:
        device = Device.objects.get(pk=data["id"])
    if device.user_id != actor.pk:
        raise DomainError("PERMISSION_DENIED", "Dispositivo no autorizado.", 403)
    if not device.active:
        raise DomainError("INVALID_STATE", "El dispositivo fue revocado.")
    # Same UUID may refresh its own display name; it never transfers ownership.
    device.name = data["name"]
    device.save(update_fields=["name", "last_contact_at"])
    return device


def receipt(operation, state, *, result=None, error=None):
    return {
        "event_id": str(operation.event_id),
        "status": state,
        "entity_id": str(operation.entity_id),
        "lock_version": (result or {}).get("lock_version"),
        "result": result or {},
        "error": error,
        "server_received_at": operation.received_at.isoformat(),
    }


def finish(operation, state, status, *, result=None, error=None):
    operation.state = state
    operation.http_status = status
    operation.response = receipt(operation, state, result=result, error=error)
    operation.save(update_fields=["state", "http_status", "response"])
    return operation.response, status


@transaction.atomic
def execute(actor, envelope, handler, authorize):
    normalized, payload_hash = normalize(envelope)
    # Account lock serializes same-account replay and coordinates revocation/password resets.
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    ensure_actor(actor)
    device = owned_device(actor, normalized["device_id"], lock=True)
    parents = list(SyncOperation.objects.filter(pk__in=normalized["depends_on"]))
    unresolved = len(parents) != len(normalized["depends_on"]) or any(
        p.state != "APLICADA" for p in parents
    )
    try:
        authorize(actor, normalized)
    except DomainError as error:
        # An entity created by a missing local parent may not exist yet. This only
        # stores a waiting intent; authorization is repeated before any effect.
        if not unresolved or error.detail["code"] not in ["NOT_FOUND", "VALIDATION_ERROR"]:
            raise
    operation = SyncOperation.objects.select_for_update().filter(pk=normalized["event_id"]).first()
    if operation is None:
        try:
            with transaction.atomic():
                operation = SyncOperation.objects.create(
                    event_id=normalized["event_id"],
                    user=actor,
                    device=device,
                    type=normalized["type"],
                    entity_id=normalized["entity_id"],
                    expected_version=normalized["expected_version"],
                    payload_hash=payload_hash,
                    payload=normalized["payload"],
                    occurred_at=normalized["occurred_at"],
                )
                SyncDependency.objects.bulk_create(
                    [
                        SyncDependency(operation=operation, depends_on_event_id=dep)
                        for dep in normalized["depends_on"]
                    ]
                )
        except IntegrityError:
            operation = SyncOperation.objects.select_for_update().get(pk=normalized["event_id"])
    if (
        operation.user_id != actor.pk
        or operation.device_id != device.pk
        or operation.payload_hash != payload_hash
    ):
        raise DomainError("IDEMPOTENCY_CONFLICT", "El UUID ya se utilizó para otra intención.")
    if operation.state in (SyncOperation.State.APLICADA, SyncOperation.State.RECHAZADA):
        return operation.response, operation.http_status
    parents = list(SyncOperation.objects.filter(pk__in=normalized["depends_on"]))
    if any(parent.user_id != actor.pk or parent.device_id != device.pk for parent in parents):
        return finish(
            operation,
            "RECHAZADA",
            403,
            error=DomainError("PERMISSION_DENIED", "Dependencia ajena.", 403).detail,
        )
    if any(not related_dependency(normalized, parent) for parent in parents):
        return finish(
            operation,
            "RECHAZADA",
            422,
            error=DomainError(
                "DEPENDENCY_UNRELATED", "Dependencia sin relación con esta intención.", 422
            ).detail,
        )
    if any(parent.state == "RECHAZADA" for parent in parents):
        return finish(
            operation,
            "RECHAZADA",
            409,
            error=DomainError("DEPENDENCY_REJECTED", "Una dependencia fue rechazada.").detail,
        )
    if len(parents) != len(normalized["depends_on"]) or any(
        parent.state != "APLICADA" for parent in parents
    ):
        return finish(
            operation,
            "ESPERA_DEPENDENCIA",
            202,
            error=DomainError(
                "DEPENDENCY_MISSING", "Falta aplicar una dependencia.", 202, retryable=True
            ).detail,
        )
    try:
        with transaction.atomic():
            result = handler(actor, normalized, operation)
            from apps.audit.services import record

            record(
                actor,
                "sync_operation",
                operation.event_id,
                normalized["type"],
                before={"expected_version": normalized["expected_version"]},
                after=result,
                operation=operation,
            )
    except DomainError as error:
        return finish(operation, "RECHAZADA", error.status_code, error=error.detail)
    return finish(operation, "APLICADA", 200, result=result)


def related_dependency(command, parent):
    if (
        str(parent.entity_id) == command["entity_id"]
        and parent.type.split("_")[0] == command["type"].split("_")[0]
    ):
        return True
    if command["type"].startswith("TRANSFER_") and parent.type == "MILKING_CONFIRM":
        lot_id = parent.payload.get("lot_id")
        if command["payload"].get("lot_id") == lot_id:
            return True
        from apps.traceability.models import TransferLine

        return TransferLine.objects.filter(
            version__transfer_id=command["entity_id"], lot_id=lot_id
        ).exists()
    return False
