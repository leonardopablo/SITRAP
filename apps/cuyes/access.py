from apps.accounts.access import active_assignments, is_admin
from apps.common.errors import DomainError

from .models import Pen, Shed, ShedGrant


def enabled_centers():
    from apps.catalog.models import CenterProduct

    return CenterProduct.objects.filter(
        enabled=True, center__active=True, center__kind="CENTRO",
        product__code="CUYES", product__active=True, product__unit_id="UN",
    ).values_list("center_id", flat=True)


def sheds_for(actor, *, operational=False):
    query = Shed.objects.filter(center_id__in=enabled_centers())
    if operational:
        query = query.filter(active=True)
    if not is_admin(actor):
        query = query.filter(id__in=ShedGrant.objects.filter(
            active=True, assignment__in=active_assignments(actor).filter(role_id="GALPONERO"),
        ).values("shed_id"))
    return query


def pens_for(actor):
    return Pen.objects.filter(shed__in=sheds_for(actor)).select_related("shed__center")


def require_pen(actor, pen, *, write=False):
    if not pens_for(actor).filter(pk=pen.pk).exists():
        raise DomainError("PERMISSION_DENIED", "Poza fuera de sus galpones autorizados.", 403)
    if write and (not pen.active or not pen.shed.active):
        raise DomainError("INVALID_STATE", "Poza o galpón inactivo.")


def require_shed(actor, shed):
    if not sheds_for(actor, operational=True).filter(pk=shed.pk).exists():
        raise DomainError("PERMISSION_DENIED", "Galpón no autorizado o Cuyes no habilitado.", 403)


def destination_pens(actor):
    # Dispatch options expose identifiers/purpose/capacity only, never foreign balances.
    # The receiving galponero still needs a current assignment at reception.
    if not sheds_for(actor, operational=True).exists():
        return Pen.objects.none()
    grants = ShedGrant.objects.filter(
        active=True,
        assignment__in=active_assignments_for_receivers(),
    ).values("shed_id")
    return Pen.objects.filter(
        active=True, shed__active=True, shed__center_id__in=enabled_centers(),
    ).filter(shed_id__in=grants).select_related("shed__center")


def active_assignments_for_receivers():
    from django.db.models import Q
    from django.utils import timezone

    from apps.accounts.models import RoleAssignment

    return RoleAssignment.objects.filter(
        role_id="GALPONERO", user__is_active=True, location__active=True,
        starts_at__lte=timezone.now(),
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=timezone.now()))
