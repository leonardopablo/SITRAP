from django.db import connection

from apps.common.errors import DomainError


def check_version(aggregate, expected_version):
    if expected_version is None:
        raise DomainError("VALIDATION_ERROR", "Se requiere expected_version.", 422)
    if aggregate.lock_version != expected_version:
        raise DomainError(
            "VERSION_CONFLICT",
            "El registro cambió; consulte su versión vigente.",
            409,
            {"expected_version": ["Versión obsoleta."]},
        )


def lock_rows(model, ids):
    if not connection.in_atomic_block:
        raise RuntimeError("Row locks require an atomic transaction.")
    return list(model.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


# All future domain services must acquire affected rows in this order.
DOMAIN_LOCK_ORDER = ("production", "lot", "transfer", "correction")
