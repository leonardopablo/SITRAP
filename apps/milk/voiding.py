from django.db import transaction
from django.utils import timezone

from apps.accounts.access import require_role
from apps.accounts.models import User
from apps.audit.services import record
from apps.common.errors import DomainError
from apps.common.services import check_version
from apps.milk.models import Milking
from apps.milk.services import milking_data
from apps.production.models import Production
from apps.sync.services import ensure_actor
from apps.traceability.models import Lot


@transaction.atomic
def void_internal(actor, milking_id, expected_version, reason, *, operation=None):
    # Internal only until B27; production lock serializes publication and voiding.
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    ensure_actor(actor)
    reference = Milking.objects.filter(pk=milking_id).first()
    if reference is None:
        raise DomainError("NOT_FOUND", "Ordeño no disponible.", 404)
    require_role(actor, "PRODUCCION", reference.center_id)
    production = Production.objects.select_for_update().get(pk=reference.production_id)
    list(Lot.objects.select_for_update().filter(production=production).order_by("id"))
    milking = Milking.objects.select_for_update().get(pk=reference.pk)
    milking.production = production
    check_version(production, expected_version)
    if production.state not in ("BORRADOR", "CONFIRMADA"):
        raise DomainError("INVALID_STATE", "La producción ya fue anulada.")
    if not isinstance(reason, str) or not reason.strip():
        raise DomainError("VALIDATION_ERROR", "Indique el motivo de anulación.", 422)
    from apps.traceability.allocation import has_active_links

    if has_active_links(production.id):
        raise DomainError("INVALID_STATE", "Producción vinculada a una entrega activa.")
    before = milking_data(milking, actor)
    production.state = "ANULADA"
    production.lock_version += 1
    production.save(update_fields=["state", "lock_version"])
    milking.voided_at = timezone.now()
    milking.save(update_fields=["voided_at"])
    result = milking_data(milking, actor)
    record(
        actor,
        "production",
        production.id,
        "VOID_MILKING",
        before=before,
        after=result,
        reason=reason.strip(),
        operation=operation,
    )
    return result
