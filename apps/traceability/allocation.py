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
    from .correction_models import Correction

    pending = Correction.objects.filter(state="PENDIENTE")
    if exclude_transfer:
        pending = pending.exclude(transfer_id=exclude_transfer)
    for correction in pending:
        old = defaultdict(Decimal)
        new = defaultdict(Decimal)
        for line in correction.original_version.lines.all():
            old[line.lot_id] += line.quantity
        for line in correction.proposed_version.lines.all():
            new[line.lot_id] += line.quantity
        for lot_id, quantity in new.items():
            totals[lot_id] += max(Decimal(0), quantity - old[lot_id])
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
