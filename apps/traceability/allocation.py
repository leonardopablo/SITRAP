from collections import defaultdict
from decimal import Decimal

from django.db.models import F

from apps.common.errors import DomainError

from .models import TransferLine


def reserved_quantities(*, exclude_transfer=None):
    lines = TransferLine.objects.filter(
        version_id=F("version__transfer__current_version_id")
    ).exclude(version__transfer__state__in=["BORRADOR", "CANCELADO"])
    if exclude_transfer:
        lines = lines.exclude(version__transfer_id=exclude_transfer)
    totals = defaultdict(Decimal)
    for lot_id, quantity in lines.values_list("lot_id", "quantity"):
        totals[lot_id] += quantity
    return totals


def check_allocation(lines, *, exclude_transfer=None):
    # Callers hold production and lot locks, shared by publication, voiding and rectification.
    totals = reserved_quantities(exclude_transfer=exclude_transfer)
    proposed = defaultdict(Decimal)
    lots = {}
    for line in lines:
        proposed[line.lot_id] += line.quantity
        lots[line.lot_id] = line.lot
    for lot_id, quantity in proposed.items():
        production = lots[lot_id].production
        if production.state != "CONFIRMADA":
            raise DomainError("INVALID_STATE", "Producción no confirmada.")
        if totals[lot_id] + quantity > production.current_version.quantity:
            raise DomainError("ALLOCATION_EXCEEDED", "La asignación supera la producción vigente.")


def has_active_links(production_id):
    return (
        TransferLine.objects.filter(
            lot__production_id=production_id, version_id=F("version__transfer__current_version_id")
        )
        .exclude(version__transfer__state__in=["BORRADOR", "CANCELADO"])
        .exists()
    )
