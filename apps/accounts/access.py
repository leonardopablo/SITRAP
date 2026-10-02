from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.accounts.models import RoleAssignment
from apps.catalog.models import Location
from apps.common.errors import DomainError

ROLE_CAPABILITIES = {
    "PRODUCCION": (
        "record_production",
        "prepare_transfer",
        "request_correction",
        "read_production",
    ),
    "TRANSPORTE": ("pickup", "approve_transport_correction", "read_assigned_transfers"),
    "RECEPCION": ("receive", "approve_reception_correction", "read_assigned_transfers"),
}
ADMIN_CAPABILITIES = (
    "manage_accounts",
    "manage_catalogs",
    "reassign_receiver",
    "read_global",
    "report_global",
)


def active_assignments(user):
    if not user or not user.is_authenticated:
        return RoleAssignment.objects.none()
    now = timezone.now()
    return (
        RoleAssignment.objects.filter(user_id=user.pk, user__is_active=True, starts_at__lte=now)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .filter(Q(location__isnull=True) | Q(location__active=True))
        .select_related("location", "role")
    )


def is_admin(user):
    return active_assignments(user).filter(role_id="ADMIN", scope="GLOBAL").exists()


def location_ids(user, role=None):
    queryset = active_assignments(user).filter(scope="UBICACION")
    if role:
        queryset = queryset.filter(role_id=role)
    return queryset.values_list("location_id", flat=True)


def visible_locations(user):
    queryset = Location.objects.filter(active=True)
    return queryset if is_admin(user) else queryset.filter(id__in=location_ids(user))


def require_admin(user):
    if not is_admin(user):
        raise DomainError("PERMISSION_DENIED", "Se requiere ADMIN global.", 403)


def require_role(user, role, location_id):
    if (
        not active_assignments(user)
        .filter(role_id=role, scope="UBICACION", location_id=location_id)
        .exists()
    ):
        raise DomainError("PERMISSION_DENIED", "No tiene permiso vigente en esta ubicación.", 403)


def require_assigned(user, role, location_id, assigned_user_id):
    require_role(user, role, location_id)
    if str(user.pk) != str(assigned_user_id):
        raise DomainError(
            "PERMISSION_DENIED", "La operación pertenece a otra persona asignada.", 403
        )


def scoped_queryset(queryset, user, role, location_field, *, admin_read=True):
    if admin_read and is_admin(user):
        return queryset
    return queryset.filter(**{f"{location_field}__in": location_ids(user, role)})


def scoped_get(queryset, **lookup):
    obj = queryset.filter(**lookup).first()
    if obj is None:
        raise NotFound("Registro no disponible.")
    return obj


def capabilities(user):
    result = []
    if user.password_change_required:
        return result
    for assignment in active_assignments(user):
        codes = (
            ADMIN_CAPABILITIES
            if assignment.role_id == "ADMIN" and assignment.scope == "GLOBAL"
            else ROLE_CAPABILITIES.get(assignment.role_id, ())
        )
        for code in codes:
            result.append({"code": code, "location_id": assignment.location_id})
    return result
