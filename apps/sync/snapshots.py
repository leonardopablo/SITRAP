import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.access import active_assignments, is_admin, location_ids
from apps.accounts.models import User
from apps.accounts.options import assignment_options
from apps.accounts.serializers import MeSerializer
from apps.audit.models import AuditEntry
from apps.audit.services import snapshot
from apps.catalog.animal_services import scoped_animals, scoped_stays
from apps.catalog.models import Location, Species, Turn
from apps.catalog.services import (
    catalog_snapshot,
    scoped_auxiliary,
    scoped_center_products,
    scoped_locations,
    scoped_presentations,
    scoped_products,
    scoped_units,
)
from apps.common.errors import DomainError
from apps.milk.services import milking_data, scoped_milkings
from apps.notifications.models import Notification
from apps.notifications.views import NotificationSerializer
from apps.traceability.corrections import CorrectionSerializer, correction_data, scoped_corrections
from apps.traceability.models import Conformity
from apps.traceability.reads import lot_data, scoped_lots, scoped_transfers, timeline, transfer_data
from apps.traceability.serializers import LotSerializer, TransferSerializer

from .models import Device, SyncSnapshot
from .services import ensure_actor, owned_device

SALT = "sitrap.sync.cursor.v1"


def scope_hash(actor):
    value = snapshot(
        list(
            active_assignments(actor)
            .order_by("id")
            .values("id", "role_id", "scope", "location_id", "starts_at", "ends_at")
        )
    )
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def collect(actor):
    entries = {}

    def add(type, id, data):
        key = f"{type}:{id}"
        entries[key] = {"entity_type": type, "id": str(id), "data": snapshot(data)}
        if len(entries) > settings.SYNC_MAX_ENTITIES:
            raise DomainError(
                "SYNC_LIMIT_EXCEEDED",
                "El conjunto excede el límite de preparación; ajuste la configuración del servidor.",
                422,
            )

    add("me", actor.id, MeSerializer(actor).data)
    for type, query in [
        ("location", scoped_locations(actor)),
        ("product", scoped_products(actor)),
        ("center_product", scoped_center_products(actor)),
        ("presentation", scoped_presentations(actor)),
        ("unit", scoped_units(actor)),
        ("species", scoped_auxiliary(actor, Species)),
        ("turn", scoped_auxiliary(actor, Turn)),
    ]:
        for obj in query.order_by("pk"):
            add(type, obj.pk, catalog_snapshot(obj))
    for animal in scoped_animals(actor).order_by("id"):
        add("animal", animal.id, catalog_snapshot(animal))
        for stay in scoped_stays(actor, animal):
            add("animal_stay", stay.id, catalog_snapshot(stay))
    centers = Location.objects.filter(active=True, kind="CENTRO")
    if not is_admin(actor):
        centers = centers.filter(pk__in=location_ids(actor, "PRODUCCION"))
    for center in centers:
        options = assignment_options(actor, center.id)
        options["receivers_by_destination"] = {
            str(destination["id"]): assignment_options(actor, center.id, destination["id"])[
                "receivers"
            ]
            for destination in options["destinations"]
        }
        options["origin_id"] = center.id
        add("assignment_options", center.id, options)
    cutoff = timezone.now() - timedelta(days=30)
    recent_transfer_ids = AuditEntry.objects.filter(
        entity_type="transfer", created_at__gte=cutoff
    ).values("entity_id")
    transfers = (
        scoped_transfers(actor)
        .filter(
            ~Q(state__in=["RECIBIDO", "CANCELADO"])
            | Q(id__in=recent_transfer_ids)
            | Q(versions__conformities__registered_at__gte=cutoff)
        )
        .distinct()
    )
    for transfer in transfers:
        add("transfer", transfer.id, TransferSerializer(transfer_data(transfer, actor)).data)
        add("timeline", transfer.id, timeline(transfer))
    for conformity in Conformity.objects.filter(version__transfer__in=transfers):
        data = catalog_snapshot(conformity)
        data["details"] = list(conformity.details.values("line_id", "accepted_quantity"))
        add("conformity", conformity.id, data)
    # Include all authorized lots, including old lots still referenced by open work.
    for lot in scoped_lots(actor).order_by("id"):
        add("lot", lot.id, LotSerializer(lot_data(lot)).data)
    for milking in scoped_milkings(actor).filter(
        Q(date__gte=cutoff.date()) | Q(production__state="BORRADOR")
    ):
        add("milking", milking.id, milking_data(milking, actor))
    for correction in scoped_corrections(actor).filter(
        Q(state="PENDIENTE") | Q(created_at__gte=cutoff) | Q(transfer__in=transfers)
    ):
        add(
            "correction",
            correction.id,
            CorrectionSerializer(correction_data(correction, actor)).data,
        )
    for note in Notification.objects.filter(recipient=actor).filter(
        Q(read_at__isnull=True) | Q(created_at__gte=cutoff)
    ):
        add("notification", note.id, NotificationSerializer(note).data)
    return entries


def token(record, kind, offset=0):
    return signing.dumps(
        {"snapshot": str(record.id), "kind": kind, "offset": offset}, salt=SALT, compress=True
    )


def resolve(value, actor, device, kind):
    try:
        data = signing.loads(value, salt=SALT)
        if data["kind"] != kind:
            raise ValueError()
        record = SyncSnapshot.objects.get(pk=data["snapshot"], device=device)
        offset = data["offset"]
        if not isinstance(offset, int) or offset < 0 or offset > len(record.changes):
            raise ValueError()
    except (signing.BadSignature, ValueError, KeyError, SyncSnapshot.DoesNotExist):
        raise DomainError("INVALID_CURSOR", "Cursor no válido para este dispositivo.", 422)
    if record.expires_at <= timezone.now():
        raise DomainError(
            "CURSOR_EXPIRED", "Descargue un nuevo bootstrap y conserve su cola local.", 410
        )
    return record, offset


@transaction.atomic
def create_snapshot(actor_id, device_id, baseline=None):
    # One PostgreSQL snapshot for the whole materialization, including permissions.
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    actor = User.objects.get(pk=actor_id)
    ensure_actor(actor)
    device = owned_device(actor, device_id)
    old = resolve(baseline, actor, device, "baseline")[0].entries if baseline else {}
    entries = collect(actor)
    changes = [
        {**entries[key], "deleted": False}
        for key in sorted(entries)
        if old.get(key) != entries[key]
    ]
    changes += [
        {
            "entity_type": old[key]["entity_type"],
            "id": old[key]["id"],
            "deleted": True,
            "data": None,
        }
        for key in sorted(old.keys() - entries.keys())
    ]
    return SyncSnapshot.objects.create(
        device=device,
        scope_hash=scope_hash(actor),
        entries=entries,
        changes=changes,
        expires_at=timezone.now() + timedelta(hours=settings.SYNC_CURSOR_TTL_HOURS),
    )


def page(actor, device_id, query, *, changes=False):
    actor = User.objects.get(pk=actor.pk)
    ensure_actor(actor)
    device = owned_device(actor, device_id)
    if query.get("page"):
        record, offset = resolve(query["page"], actor, device, "page")
        if record.scope_hash != scope_hash(actor):
            raise DomainError(
                "CURSOR_SCOPE_CHANGED",
                "Cambió el acceso durante la descarga. Reinicie desde el último cursor completo o bootstrap.",
                409,
            )
    else:
        if changes and not query.get("cursor"):
            raise DomainError(
                "VALIDATION_ERROR", "Se requiere cursor de la última descarga completa.", 422
            )
        record = create_snapshot(actor.id, device.id, query.get("cursor") if changes else None)
        offset = 0
    end = min(offset + query["limit"], len(record.changes))
    finished = end == len(record.changes)
    if finished:
        now = timezone.now()
        expires = now + timedelta(days=settings.OFFLINE_PREPARATION_DAYS)
        Device.objects.filter(pk=device.pk, active=True).update(
            prepared_at=now, preparation_expires_at=expires, last_contact_at=now
        )
        device.preparation_expires_at = expires
    return {
        "snapshot_at": record.created_at,
        "expires_at": record.expires_at,
        "preparation_expires_at": device.preparation_expires_at,
        "results": record.changes[offset:end],
        "next_page": None if finished else token(record, "page", end),
        "cursor": token(record, "baseline") if finished else None,
    }
