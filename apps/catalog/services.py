import uuid

from django.db import IntegrityError, transaction

from apps.accounts.access import is_admin, location_ids, require_admin
from apps.accounts.models import User
from apps.audit.services import record
from apps.catalog.models import CenterProduct, Location, Presentation, Product, Unit
from apps.common.errors import DomainError
from apps.sync.services import ensure_actor


def scoped_locations(user):
    return (
        Location.objects.all()
        if is_admin(user)
        else Location.objects.filter(active=True, id__in=location_ids(user))
    )


def scoped_products(user):
    if is_admin(user):
        return Product.objects.all()
    return Product.objects.filter(
        active=True,
        centerproduct__enabled=True,
        centerproduct__center__active=True,
        centerproduct__center_id__in=location_ids(user),
    ).distinct()


def scoped_center_products(user):
    if is_admin(user):
        return CenterProduct.objects.all()
    return CenterProduct.objects.filter(
        enabled=True,
        center__active=True,
        product__active=True,
        center_id__in=location_ids(user),
    )


def catalog_snapshot(obj):
    return {field.attname: getattr(obj, field.attname) for field in obj._meta.concrete_fields}


@transaction.atomic
def save_catalog(actor, model, data, *, pk=None, immutable=()):
    actor = User.objects.select_for_update().get(pk=actor.pk)
    ensure_actor(actor)
    require_admin(actor)
    creating = pk is None
    key = data.get(model._meta.pk.attname) if creating else pk
    obj = model.objects.select_for_update().filter(pk=key).first()
    if not creating and obj is None:
        raise DomainError("NOT_FOUND", "Registro no disponible.", 404)
    if creating and obj is not None:
        if all(getattr(obj, name) == value for name, value in data.items()):
            return obj
        raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de catálogo ya utilizado.")
    if not creating:
        if any(name in data and getattr(obj, name) != data[name] for name in ("id", *immutable)):
            raise DomainError(
                "VALIDATION_ERROR", "No se puede cambiar la identidad del catálogo.", 422
            )
    before = catalog_snapshot(obj) if obj else {}
    obj = obj or model()
    for name, value in data.items():
        setattr(obj, name, value)
    obj.full_clean()
    if isinstance(obj, CenterProduct):
        if obj.center.kind != "CENTRO":
            raise DomainError("VALIDATION_ERROR", "Se requiere un centro de producción.", 422)
        if obj.enabled and (not obj.center.active or not obj.product.active):
            raise DomainError("VALIDATION_ERROR", "Centro o producto inactivo.", 422)
    after = catalog_snapshot(obj)
    if before != after:
        try:
            with transaction.atomic():
                obj.save()
        except IntegrityError:
            raise DomainError("VALIDATION_ERROR", "Código o relación de catálogo duplicados.", 422)
        record(
            actor,
            model._meta.model_name,
            obj.pk
            if isinstance(obj.pk, uuid.UUID)
            else uuid.uuid5(uuid.NAMESPACE_URL, f"{model._meta.label}/{obj.pk}"),
            "SAVE_CATALOG",
            before=before,
            after=after,
        )
    return obj


def scoped_presentations(user):
    if is_admin(user):
        return Presentation.objects.all()
    return Presentation.objects.filter(active=True, product__in=scoped_products(user))


def scoped_units(user):
    if is_admin(user):
        return Unit.objects.all()
    return Unit.objects.filter(pk__in=scoped_products(user).values("unit_id"))


def scoped_auxiliary(user, model):
    if is_admin(user):
        return model.objects.all()
    return (
        model.objects.filter(active=True)
        if location_ids(user, "PRODUCCION").exists()
        else model.objects.none()
    )
