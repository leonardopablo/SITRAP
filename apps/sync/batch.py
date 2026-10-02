import heapq
import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.common.errors import DomainError
from apps.common.serializers import StrictSerializer

from .commands import dispatch, registry
from .models import SyncDependency, SyncOperation
from .serializers import EnvelopeSerializer
from .services import ensure_actor, normalize, owned_device

OFFLINE_TYPES = {
    "MILKING_CREATE",
    "MILKING_UPDATE",
    "MILKING_CONFIRM",
    "TRANSFER_CREATE",
    "TRANSFER_UPDATE",
    "TRANSFER_SEND",
    "TRANSFER_PICKUP",
    "TRANSFER_RECEIVE",
    "CORRECTION_ACCEPT",
    "CORRECTION_REJECT",
}


class BatchInput(StrictSerializer):
    events = EnvelopeSerializer(many=True, max_length=100, allow_empty=False)


def reconstruct(operation):
    return {
        "event_id": str(operation.event_id),
        "device_id": str(operation.device_id),
        "entity_id": str(operation.entity_id),
        "type": operation.type,
        "expected_version": operation.expected_version,
        "occurred_at": operation.occurred_at.isoformat(),
        "depends_on": [
            str(id) for id in operation.dependencies.values_list("depends_on_event_id", flat=True)
        ],
        "payload": operation.payload,
    }


def validate_batch(data):
    serializer = BatchInput(data=data)
    serializer.is_valid(raise_exception=True)
    events, hashes = [], {}
    for event in serializer.validated_data["events"]:
        if event["type"] not in OFFLINE_TYPES:
            raise DomainError("ONLINE_ONLY", "Esta acción requiere el endpoint online.", 422)
        typed = registry()[event["type"]][0](data=event)
        typed.is_valid(raise_exception=True)
        normalized, fingerprint = normalize(typed.validated_data)
        key = normalized["event_id"]
        if key in hashes and hashes[key] != fingerprint:
            raise DomainError("VALIDATION_ERROR", "Un UUID aparece con contenidos distintos.", 422)
        hashes[key] = fingerprint
        events.append(normalized)
    if len({e["device_id"] for e in events}) != 1:
        raise DomainError("VALIDATION_ERROR", "El lote debe pertenecer a un dispositivo.", 422)
    if len(json.dumps(events).encode()) > settings.SYNC_MAX_BATCH_BYTES:
        raise DomainError("VALIDATION_ERROR", "Lote demasiado grande.", 422)
    return events


def topological(commands):
    outgoing = {id: [] for id in commands}
    degrees = {id: 0 for id in commands}
    for id, event in commands.items():
        for parent in event["depends_on"]:
            if parent in commands:
                outgoing[parent].append(id)
                degrees[id] += 1
    ready = [id for id, degree in degrees.items() if degree == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        id = heapq.heappop(ready)
        result.append(id)
        for child in outgoing[id]:
            degrees[child] -= 1
            if degrees[child] == 0:
                heapq.heappush(ready, child)
    if len(result) != len(commands):
        raise DomainError("DEPENDENCY_CYCLE", "Las dependencias contienen un ciclo.", 422)
    return result


@transaction.atomic
def process(actor, events):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    ensure_actor(actor)
    device = owned_device(actor, events[0]["device_id"])
    waiting = SyncOperation.objects.filter(
        user=actor, device=device, state="ESPERA_DEPENDENCIA", type__in=OFFLINE_TYPES
    ).order_by("received_at", "event_id")[: settings.SYNC_RETRY_WAITING_LIMIT]
    commands = {str(op.event_id): reconstruct(op) for op in waiting}
    incoming = {e["event_id"]: e for e in events}
    commands.update(incoming)
    pending_ids = list(
        SyncOperation.objects.filter(
            user=actor, device=device, state="ESPERA_DEPENDENCIA"
        ).values_list("event_id", flat=True)[:10001]
    )
    if len(pending_ids) > 10000:
        raise DomainError(
            "SYNC_LIMIT_EXCEEDED", "Demasiadas dependencias pendientes para resolver el grafo.", 422
        )
    graph = {str(id): {"depends_on": []} for id in pending_ids}
    for child, parent in SyncDependency.objects.filter(operation_id__in=pending_ids).values_list(
        "operation_id", "depends_on_event_id"
    ):
        graph[str(child)]["depends_on"].append(str(parent))
    graph.update(commands)
    order = [id for id in topological(graph) if id in commands]
    results = {}
    for id in order:
        command = commands[id]
        try:
            body, http_status = dispatch(actor, command)
            results[id] = {**body, "http_status": http_status, "persisted": True}
        except DomainError as exc:
            results[id] = {
                "event_id": id,
                "entity_id": command["entity_id"],
                "status": "NO_PROCESADA",
                "lock_version": None,
                "result": {},
                "error": exc.detail,
                "server_received_at": timezone.now().isoformat(),
                "http_status": exc.status_code,
                "persisted": False,
            }
    return {
        "results": [results[e["event_id"]] for e in events],
        "reprocessed": [results[id] for id in order if id not in incoming],
    }
