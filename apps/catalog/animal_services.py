from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.access import is_admin, location_ids, require_role
from apps.accounts.models import User
from apps.audit.services import record
from apps.catalog.models import Animal, AnimalStay, Location
from apps.catalog.services import catalog_snapshot
from apps.common.errors import DomainError
from apps.sync.services import ensure_actor


def scoped_animals(actor):
    if is_admin(actor):
        return Animal.objects.all()
    return Animal.objects.filter(
        pk__in=AnimalStay.objects.filter(center_id__in=location_ids(actor, "PRODUCCION")).values(
            "animal_id"
        )
    )


def scoped_stays(actor, animal):
    queryset = animal.stays.order_by("starts_on", "id")
    return (
        queryset
        if is_admin(actor)
        else queryset.filter(center_id__in=location_ids(actor, "PRODUCCION"))
    )


def require_center(actor, center_id):
    if not is_admin(actor):
        require_role(actor, "PRODUCCION", center_id)
    center = Location.objects.filter(pk=center_id, kind="CENTRO", active=True).first()
    if center is None:
        raise DomainError("VALIDATION_ERROR", "Centro no disponible.", 422)
    return center


@transaction.atomic
def create_animal(actor, data):
    actor = User.objects.select_for_update().get(pk=actor.pk)
    ensure_actor(actor)
    require_center(actor, data["center_id"])
    fields = {key: data[key] for key in ("id", "code", "species_id", "sex", "name", "status")}
    existing = Animal.objects.filter(pk=data["id"]).first()
    if existing:
        stay = existing.stays.filter(
            pk=data["stay_id"], center_id=data["center_id"], starts_on=data["starts_on"]
        ).first()
        if stay and all(getattr(existing, key) == value for key, value in fields.items()):
            return existing
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de animal ya utilizado.")
    animal = Animal(**fields)
    animal.full_clean()
    if not animal.species.active:
        raise DomainError("VALIDATION_ERROR", "Especie inactiva.", 422)
    try:
        with transaction.atomic():
            animal.save(force_insert=True)
            stay = AnimalStay(
                id=data["stay_id"],
                animal=animal,
                center_id=data["center_id"],
                starts_on=data["starts_on"],
            )
            stay.full_clean()
            stay.save(force_insert=True)
    except IntegrityError:
        raise DomainError("VALIDATION_ERROR", "Código o UUID duplicado.", 422)
    record(actor, "animal", animal.id, "CREATE_ANIMAL", after=catalog_snapshot(animal))
    record(actor, "animal_stay", stay.id, "CREATE_STAY", after=catalog_snapshot(stay))
    return animal


@transaction.atomic
def update_animal(actor, animal_id, data):
    actor = User.objects.select_for_update().get(pk=actor.pk)
    ensure_actor(actor)
    animal = scoped_animals(actor).select_for_update().filter(pk=animal_id).first()
    if animal is None:
        raise DomainError("NOT_FOUND", "Animal no disponible.", 404)
    if not is_admin(actor):
        today = timezone.localdate()
        current = (
            animal.stays.filter(starts_on__lte=today)
            .filter(Q(ends_on__isnull=True) | Q(ends_on__gt=today))
            .first()
        )
        if current is None:
            raise DomainError(
                "PERMISSION_DENIED", "El animal no está actualmente en su centro.", 403
            )
        require_role(actor, "PRODUCCION", current.center_id)
    before = catalog_snapshot(animal)
    for key, value in data.items():
        setattr(animal, key, value)
    animal.full_clean()
    after = catalog_snapshot(animal)
    if before != after:
        animal.save(update_fields=list(data))
        record(actor, "animal", animal.id, "UPDATE_ANIMAL", before=before, after=after)
    return animal


@transaction.atomic
def add_stay(actor, animal_id, data):
    actor = User.objects.select_for_update().get(pk=actor.pk)
    ensure_actor(actor)
    require_center(actor, data["center_id"])
    animal = scoped_animals(actor).select_for_update().filter(pk=animal_id).first()
    if animal is None:
        raise DomainError("NOT_FOUND", "Animal no disponible.", 404)
    previous = AnimalStay.objects.filter(pk=data["id"]).first()
    if previous:
        if previous.animal_id == animal.pk and all(
            getattr(previous, key) == value for key, value in data.items()
        ):
            return previous
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de estancia ya utilizado.")
    if not is_admin(actor) and animal.stays.exclude(center_id=data["center_id"]).exists():
        raise DomainError("PERMISSION_DENIED", "Solo ADMIN mueve animales entre centros.", 403)
    # A move closes the previous open interval in this same transaction.
    open_stay = animal.stays.filter(ends_on__isnull=True).first()
    if open_stay and open_stay.center_id != data["center_id"]:
        if not is_admin(actor):
            raise DomainError("PERMISSION_DENIED", "Solo ADMIN mueve animales entre centros.", 403)
        if data["starts_on"] <= open_stay.starts_on:
            raise DomainError("VALIDATION_ERROR", "La nueva estancia debe ser posterior.", 422)
        before = catalog_snapshot(open_stay)
        open_stay.ends_on = data["starts_on"]
        open_stay.save(update_fields=["ends_on"])
        record(
            actor,
            "animal_stay",
            open_stay.id,
            "CLOSE_STAY",
            before=before,
            after=catalog_snapshot(open_stay),
        )
    stay = AnimalStay(animal=animal, **data)
    stay.full_clean()
    try:
        with transaction.atomic():
            stay.save(force_insert=True)
    except IntegrityError:
        raise DomainError("VALIDATION_ERROR", "Las estancias no pueden superponerse.", 422)
    record(actor, "animal_stay", stay.id, "CREATE_STAY", after=catalog_snapshot(stay))
    return stay
