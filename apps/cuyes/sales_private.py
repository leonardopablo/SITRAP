import hashlib
import io
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from PIL import Image

from apps.accounts.access import require_admin
from apps.accounts.models import User
from apps.audit.services import record
from apps.sync.services import ensure_actor, execute

from .models import PaymentEvidence, SaleDelivery
from .sales_services import (
    PAID,
    expect_version,
    lock_order,
    physical_dispatch,
    require_state,
    require_worker,
    revision,
)
from .services import fail, get


def storage():
    return FileSystemStorage(location=settings.CUY_SALES_PRIVATE_ROOT)


@transaction.atomic
def upload_evidence(actor, data):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.id)
    require_admin(actor)
    uploaded = data["file"]
    maximum = settings.CUY_SALES_MAX_VOUCHER_BYTES
    if uploaded.size > maximum:
        fail("Comprobante demasiado grande (máximo configurado: 5 MiB).", "VALIDATION_ERROR", 422)
    content = uploaded.read(maximum + 1)
    if len(content) > maximum:
        fail("Comprobante demasiado grande.", "VALIDATION_ERROR", 422)
    if content.startswith(b"%PDF-"):
        if not content.rstrip().endswith(b"%%EOF"):
            fail("El PDF no está completo.", "VALIDATION_ERROR", 422)
        extension, mime = "pdf", "application/pdf"
    else:
        try:
            image = Image.open(io.BytesIO(content))
            if image.format not in ["PNG", "JPEG"] or image.width * image.height > 20000000:
                raise ValueError()
            extension, mime = ("png", "image/png") if image.format == "PNG" else ("jpg", "image/jpeg")
            image.verify()
        except (ValueError, OSError, Image.DecompressionBombError):
            fail("Solo se admite PDF, JPEG o PNG válido.", "VALIDATION_ERROR", 422)
    digest = hashlib.sha256(content).hexdigest()
    previous = PaymentEvidence.objects.filter(pk=data["id"]).first()
    if previous:
        if previous.uploader_id != actor.id or previous.digest != digest:
            fail("UUID de comprobante ya utilizado.", "IDEMPOTENCY_CONFLICT")
        return previous
    name = storage().save(f"{data['id']}.{extension}", ContentFile(content))
    try:
        evidence = PaymentEvidence.objects.create(
            id=data["id"], uploader=actor, storage_name=name,
            digest=digest, content_type=mime, size=len(content),
        )
        record(actor, "cuy_voucher", evidence.id, "UPLOAD_EVIDENCE", after={"size": evidence.size})
    except Exception:
        storage().delete(name)
        raise
    return evidence


def download_evidence(actor, evidence_id):
    require_admin(actor)
    evidence = get(PaymentEvidence, evidence_id)
    if not storage().exists(evidence.storage_name):
        fail("Comprobante no disponible; contacte al administrador.", "NOT_FOUND", 404)
    extension = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[evidence.content_type]
    response = FileResponse(
        storage().open(evidence.storage_name, "rb"), as_attachment=True,
        filename=f"comprobante-{evidence.id}.{extension}", content_type=evidence.content_type,
    )
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


@sensitive_variables("pin")
@transaction.atomic
def generate_pin(actor, order_id, data):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.id)
    ensure_actor(actor)
    require_admin(actor)
    order = lock_order(order_id)
    expect_version(order, data)
    require_state(order, PAID)
    if order.mode != "DIRECTO" or order.financial_hold:
        fail("PIN disponible solo para recojo directo pagado y sin revisión económica.")
    pin = f"{secrets.randbelow(100000000):08d}"
    while order.pin_hash and check_password(pin, order.pin_hash):
        pin = f"{secrets.randbelow(100000000):08d}"
    order.pin_hash = make_password(pin)
    order.pin_generation += 1
    order.pin_failures = 0
    order.pin_generated_at, order.pin_consumed_at = timezone.now(), None
    revision(actor, order, "SALE_PIN_GENERATED", data["reason"])
    return {"pin": pin, "version": order.version, "message": "Se muestra una sola vez. Entréguelo al cliente fuera de avisos y URL."}


@sensitive_variables()
def deliver_with_pin(actor, order_id, data):
    candidate = data["pin"]
    # The secret is intentionally never part of an Envelope/SyncOperation/audit.
    envelope = {
        "event_id": data["event_id"], "device_id": data["device_id"], "entity_id": order_id,
        "type": "SALE_DIRECT", "occurred_at": timezone.now().isoformat(), "depends_on": [],
        "expected_version": data["expected_version"],
        "payload": {
            "reason": data["reason"], "physical_responsible": data["physical_responsible"],
            "reference": data["reference"],
        },
    }
    # A retry must reconstruct the same envelope even if its HTTP request arrives later.
    # occurred_at is stable per event, without persisting any candidate PIN.
    from apps.sync.models import SyncOperation

    previous = SyncOperation.objects.filter(pk=data["event_id"]).first()
    if previous:
        envelope["occurred_at"] = previous.occurred_at.isoformat()

    def authorize(current_actor, command):
        from .models import SaleOrder

        require_worker(current_actor, get(SaleOrder, order_id))

    @sensitive_variables()
    def handler(current_actor, command, operation):
        order = lock_order(order_id)
        require_worker(current_actor, order)
        expect_version(order, command)
        require_state(order, PAID)
        if order.mode != "DIRECTO" or not order.pin_hash or order.pin_consumed_at:
            fail("PIN no disponible o ya consumido.", "PIN_UNAVAILABLE")
        if order.pin_failures >= settings.CUY_SALES_PIN_ATTEMPTS:
            fail("PIN bloqueado por intentos. ADMIN debe regenerarlo.", "PIN_LOCKED", 429)
        if not check_password(candidate, order.pin_hash):
            order.pin_failures += 1
            order.save(update_fields=["pin_failures"])
            record(current_actor, "cuy_sale", order.id, "SALE_PIN_FAILED",
                   after={"attempts": order.pin_failures}, operation=operation)
            # Business error is returned, not raised: the attempt counter must commit.
            return {"order_id": str(order.id), "pin_valid": False, "code": "PIN_INVALID"}
        physical_dispatch(current_actor, order, operation, data["reason"], direct=True)
        order.pin_hash, order.pin_consumed_at = "", timezone.now()
        SaleDelivery.objects.create(
            order=order, stage="ENTREGA_CLIENTE", registered_by=current_actor,
            physical_responsible=data["physical_responsible"], reference=data["reference"],
        )
        return {**revision(current_actor, order, "SALE_DIRECT_DELIVERED", data["reason"], operation), "pin_valid": True}

    return execute(actor, envelope, handler, authorize)
