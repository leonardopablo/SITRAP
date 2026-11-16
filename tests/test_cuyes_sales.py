import io
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, connections, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEntry
from apps.catalog.models import Location
from apps.common.errors import DomainError
from apps.cuyes.models import (
    DispatchSelection,
    Movement,
    Occupation,
    Pen,
    SaleConformity,
    SaleDelivery,
    SaleDispatch,
    SaleFinancialReview,
    SaleLine,
    SaleOrder,
    SalePayment,
    SaleReservation,
    Shed,
    ShedGrant,
)
from apps.cuyes.sales_private import deliver_with_pin, generate_pin, upload_evidence
from apps.cuyes.sales_reads import availability_data, order_data
from apps.cuyes.sales_services import expire_one, save_module
from apps.cuyes.services import total
from apps.notifications.models import Notification
from apps.sync.commands import dispatch
from apps.sync.models import Device, SyncOperation
from tests.test_access import assign
from tests.test_cuyes import (
    farm,  # noqa: F401
    item,
    send,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def market(farm, settings, tmp_path):  # noqa: F811 -- shared pytest fixture
    settings.CUY_SALES_PRIVATE_ROOT = tmp_path / "private-sales"
    f = farm
    send(f["worker"], "OPEN", pen_id=str(f["p1"].id), lot={"provenance": "Conteo físico de prueba"},
         items=[item(category="MACHO", quality="A", quantity=8), item(category="HEMBRA", quality="A", quantity=20)])
    f["occupation"] = Occupation.objects.get(pen=f["p1"])
    driver = User.objects.create_user(username="driver-sale", name="Conductor")
    assign(driver, "TRANSPORTE", f["can"])
    f["driver"] = driver
    f["point"] = Location.objects.create(code="PV", name="Punto de venta", kind="PUNTO_VENTA")
    f["module"] = save_module(f["admin"], {
        "id": uuid.uuid4(), "name": "1M + 3H", "active": True, "reason": "Receta aprobada",
        "components": [{"category": "MACHO", "quality": "A", "quantity": 1},
                       {"category": "HEMBRA", "quality": "A", "quantity": 3}],
    })
    return f


def command(actor, kind, order=None, **payload):
    device = Device.objects.filter(user=actor).first() or Device.objects.create(user=actor, name="Comercial")
    c = {
        "event_id": str(uuid.uuid4()), "device_id": str(device.id), "entity_id": str(order.id if order else uuid.uuid4()),
        "type": f"SALE_{kind}", "occurred_at": timezone.now().isoformat(), "depends_on": [],
        "payload": {"reason": "Hecho comercial comprobado", **payload},
    }
    if order:
        order.refresh_from_db()
        c["expected_version"] = order.version
    return c


def act(f, kind, actor=None, order=None, **payload):
    c = command(actor or f["admin"], kind, order, **payload)
    body, status = dispatch(actor or f["admin"], c)
    assert status == 200, body
    if order:
        order.refresh_from_db()
    return body, c


def line(kind="UNIDAD", units=1, category="MACHO", **kwargs):
    return {
        "id": str(uuid.uuid4()), "kind": kind, "units": units, "unit_price": "10.00",
        **({"category": category, "quality": "A"} if kind != "MODULO" else {}),
        **kwargs,
    }


def create(f, *, mode="DIRECTO", items=None):
    body, c = act(f, "CREATE", center_id=str(f["can"].id), mode=mode,
                  client_name="Cliente ficticio", client_contact="000-TEST",
                  **({"point_id": str(f["point"].id)} if mode == "PUNTO" else {}),
                  items=items or [line()])
    return SaleOrder.objects.get(pk=body["result"]["order_id"]), c


def evidence(f):
    return upload_evidence(f["admin"], {
        "id": uuid.uuid4(), "file": SimpleUploadedFile("voucher.pdf", b"%PDF-1.4\n% ficticio\n%%EOF", content_type="application/pdf"),
    })


def pay(f, order):
    act(f, "PAY", order=order, amount=str(order.total), currency=order.currency,
        method="Transferencia", reference="PAGO-TEST", evidence_id=str(evidence(f).id))


def prepare(f, order, *, actor=None, occ=None, sheds=None):
    actor = actor or f["worker"]
    occ = occ or f["occupation"]
    items = [
        {"line_id": str(sale_line.id), "occupation_id": str(occ.id), "category": c["category"],
         "quality": c["quality"], "quantity": c["quantity"] * sale_line.units}
        for sale_line in order.lines.all() for c in sale_line.recipe
    ]
    act(f, "SELECT", actor=actor, order=order, shed_ids=[str(s.id) for s in (sheds or [f["g1"]])], items=items)
    return items


def origin(f, order, actor=None, sheds=None):
    act(f, "ORIGIN", actor=actor or f["worker"], order=order,
        preparation_id=str(order.preparation_id), round=order.confirmation_round,
        shed_ids=[str(s.id) for s in (sheds or [f["g1"]])])


def pin_data(f, order, pin, event=None):
    device = Device.objects.filter(user=f["worker"]).first() or Device.objects.create(user=f["worker"], name="PIN")
    return dict(event_id=event or uuid.uuid4(), device_id=device.id, expected_version=order.version,
                pin=pin, reason="Retiro físico comprobado", physical_responsible="Galponero de prueba", reference="Cliente acredita retiro")


def test_kits_scarce_component_and_aggregate_atomic_reservation(market):
    f = market
    assert availability_data(f["admin"], f["can"].id, "ADMIN")["modules"][0]["offerable"] == 6
    order, _ = create(f, items=[line("MODULO", units=6, module_id=str(f["module"].id)), line(units=3)])
    result, status = dispatch(f["worker"], command(f["worker"], "CONFIRM", order))
    assert status == 409 and result["error"]["code"] == "INSUFFICIENT_AVAILABLE"
    assert not SaleReservation.objects.exists()
    assert total(f["p1"]) == 28
    # Catalog changes do not rewrite the copied 1+3 recipe.
    save_module(f["admin"], {"id": f["module"].id, "name": "1M + 7H", "active": True, "reason": "Nueva receta",
                            "components": [{"category": "MACHO", "quality": "A", "quantity": 1}, {"category": "HEMBRA", "quality": "A", "quantity": 7}]})
    assert SaleLine.objects.filter(order=order, kind="MODULO").get().recipe[1]["quantity"] in [1, 3]
    assert sum(c["quantity"] for c in order.lines.get(kind="MODULO").recipe) == 4


def test_request_confirm_pay_replay_no_early_deduction(market):
    f = market
    order, create_command = create(f)
    assert dispatch(f["admin"], create_command)[1] == 200
    assert SaleOrder.objects.count() == 1
    assert Notification.objects.filter(type="SALE_REQUESTED").count() == 1
    body, confirm = act(f, "CONFIRM", actor=f["worker"], order=order)
    assert dispatch(f["worker"], confirm) == (body, 200)
    assert order.reservations.get().state == "IMPAGA" and total(f["p1"]) == 28
    payment, c = act(f, "PAY", order=order, amount=str(order.total), currency="PEN",
                     method="Transferencia", reference="TEST", evidence_id=str(evidence(f).id))
    assert dispatch(f["admin"], c) == (payment, 200)
    assert SalePayment.objects.count() == 1
    assert order.reservations.get().state == "PAGADA"
    assert total(f["p1"]) == 28


def test_expiration_effective_on_api_and_idempotent_management(market, api):
    f = market
    order, _ = create(f)
    act(f, "CONFIRM", actor=f["worker"], order=order)
    reserve = order.reservations.get()
    reserve.expires_at = timezone.now() - timedelta(seconds=1)
    reserve.save()
    api.force_login(f["admin"])
    assert api.get(f"/api/v1/cuyes/sales/orders/{order.id}?workspace=ADMIN").json()["display_state"] == "RESERVA_VENCIDA"
    result, status = dispatch(f["admin"], command(f["admin"], "PAY", order, amount=str(order.total),
        currency="PEN", method="Efectivo", reference="TEST", evidence_id=str(evidence(f).id)))
    assert status == 409 and result["error"]["code"] == "RESERVATION_EXPIRED"
    assert not SalePayment.objects.exists()
    for _ in range(2):
        call_command("expire_cuy_sales", username=f["admin"].username, stdout=io.StringIO())
    reserve.refresh_from_db()
    assert reserve.state == "VENCIDA"
    assert Notification.objects.filter(type="SALE_EXPIRED").count() == 1
    assert total(f["p1"]) == 28


def test_direct_pin_wrong_correct_replay_consumption_and_no_secret_storage(market, api):
    f = market
    order, _ = create(f, items=[line("MODULO", module_id=str(f["module"].id))])
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    generated = generate_pin(f["admin"], order.id, {"expected_version": order.version, "reason": "Entregado fuera de app"})
    order.refresh_from_db()
    first_pin = generated["pin"]
    regenerated = generate_pin(f["admin"], order.id, {"expected_version": order.version, "reason": "Regeneración"})
    order.refresh_from_db()
    old, _ = deliver_with_pin(f["worker"], order.id, pin_data(f, order, first_pin))
    assert old["result"]["pin_valid"] is False
    prepare(f, order)
    origin(f, order)
    invalid, _ = deliver_with_pin(f["worker"], order.id, pin_data(f, order, "xxxxxxxx"))
    assert invalid["result"]["pin_valid"] is False
    order.refresh_from_db()
    assert order.pin_failures == 2
    data = pin_data(f, order, regenerated["pin"])
    receipt = deliver_with_pin(f["worker"], order.id, data)
    assert receipt[1] == 200 and receipt[0]["result"]["pin_valid"]
    assert deliver_with_pin(f["worker"], order.id, data) == receipt
    assert total(f["p1"]) == 24 and SaleDispatch.objects.count() == 1
    order.refresh_from_db()
    assert order.state == "ENTREGADO" and not order.pin_hash and order.pin_consumed_at
    rejected, status = deliver_with_pin(f["worker"], order.id, pin_data(f, order, regenerated["pin"]))
    assert status == 409
    assert SaleDelivery.objects.count() == 1
    serialized = str(list(AuditEntry.objects.values())) + str(list(SyncOperation.objects.values()))
    assert first_pin not in serialized and regenerated["pin"] not in serialized and "xxxxxxxx" not in serialized
    api.force_login(f["driver"])
    assert api.get("/api/v1/cuyes/sales/orders?workspace=TRANSPORTE").json()["results"] == []
    assert api.get(f"/api/v1/cuyes/sales/orders/{order.id}?workspace=TRANSPORTE").status_code == 404


def test_pin_attempt_limit_and_regeneration(market, settings):
    f = market
    settings.CUY_SALES_PIN_ATTEMPTS = 2
    order, _ = create(f)
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    generate_pin(f["admin"], order.id, {"expected_version": order.version, "reason": "Ticket"})
    order.refresh_from_db()
    data = pin_data(f, order, "invalid")
    assert deliver_with_pin(f["worker"], order.id, data)[0]["result"]["pin_valid"] is False
    deliver_with_pin(f["worker"], order.id, data)
    order.refresh_from_db()
    assert order.pin_failures == 1
    deliver_with_pin(f["worker"], order.id, pin_data(f, order, "invalid"))
    result, status = deliver_with_pin(f["worker"], order.id, pin_data(f, order, "invalid"))
    assert status == 429 and result["error"]["code"] == "PIN_LOCKED"
    generate_pin(f["admin"], order.id, {"expected_version": order.version, "reason": "Recuperación segura"})
    order.refresh_from_db()
    assert order.pin_failures == 0


def test_transport_conformities_unique_departure_arrival_collection(market, api):
    f = market
    order, _ = create(f, mode="PUNTO", items=[line(units=2)])
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    act(f, "DRIVER", order=order, driver_id=str(f["driver"].id))
    prepare(f, order)
    origin(f, order)
    failed, status = dispatch(f["worker"], command(f["worker"], "DEPART", order))
    assert status == 409 and failed["error"]["code"] == "DRIVER_CONFIRMATION_REQUIRED"
    assert total(f["p1"]) == 28
    act(f, "PICKUP", actor=f["driver"], order=order, preparation_id=str(order.preparation_id), round=order.confirmation_round, shed_ids=[])
    body, c = act(f, "DEPART", actor=f["worker"], order=order)
    assert dispatch(f["worker"], c) == (body, 200)
    assert total(f["p1"]) == 26
    act(f, "ARRIVE", actor=f["driver"], order=order, delivered_to_client=False, physical_responsible="Conductor ficticio", reference="Dejado a encargado")
    assert order.state == "EN_PUNTO" and total(f["p1"]) == 26
    act(f, "COLLECT", order=order, physical_responsible="Encargado que acreditó entrega", reference="Retiró cliente ficticio")
    assert order.state == "ENTREGADO" and total(f["p1"]) == 26
    assert SaleDelivery.objects.get(stage="ENTREGA_CLIENTE").registered_by_id == f["admin"].id
    detail = order.dispatch.details.get()
    assert detail.snapshot["pen"] == f["p1"].code and detail.snapshot["lot_id"] == str(f["occupation"].lot_id)
    assert "age_days_min" in detail.snapshot
    api.force_login(f["driver"])
    data = api.get(f"/api/v1/cuyes/sales/orders/{order.id}?workspace=TRANSPORTE").json()
    assert "total" not in data and "payment" not in data and "unit_price" not in data["lines"][0] and "pin_status" not in data


def test_changed_selection_invalidates_both_conformities(market):
    f = market
    order, _ = create(f, mode="PUNTO")
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    act(f, "DRIVER", order=order, driver_id=str(f["driver"].id))
    prepare(f, order)
    origin(f, order)
    act(f, "PICKUP", actor=f["driver"], order=order, preparation_id=str(order.preparation_id), round=order.confirmation_round, shed_ids=[])
    old = order.preparation_id
    prepare(f, order)
    assert order.preparation_id != old and SaleConformity.objects.count() == 2
    failed, status = dispatch(f["worker"], command(f["worker"], "DEPART", order))
    assert status == 409 and failed["error"]["code"] == "ORIGIN_CONFIRMATION_REQUIRED"


def test_weight_difference_preserves_payment_and_requires_financial_resolution(market):
    f = market
    order, _ = create(f, items=[line("PESO", units=2, weight_kg="2.500", weight_basis="VIVO")])
    assert order.lines.get().animal_count == 2 and order.total == Decimal("25")
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    pin = generate_pin(f["admin"], order.id, {"expected_version": order.version, "reason": "Ticket inicial"})["pin"]
    order.refresh_from_db()
    act(f, "WEIGH", order=order, line_id=str(order.lines.get().id), weight_kg="3.000")
    assert order.total == Decimal("30") and order.financial_hold
    assert order.payment.amount == Decimal("25")
    prepare(f, order)
    origin(f, order)
    blocked, status = deliver_with_pin(f["worker"], order.id, pin_data(f, order, pin))
    assert status == 409 and blocked["error"]["code"] == "FINANCIAL_REVIEW_REQUIRED"
    act(f, "FINANCE", order=order, treatment="COBRO_ADICIONAL", evidence_id=str(evidence(f).id), reference="Diferencia cobrada manualmente")
    assert not order.financial_hold and order.approved_total == Decimal("30")
    assert SaleFinancialReview.objects.get().difference == Decimal("5")
    assert total(f["p1"]) == 28


def test_selection_claims_do_not_assign_the_same_pen_twice(market):
    f = market
    send(f["worker"], "OPEN", pen_id=str(f["pm"].id), lot={"provenance": "Segundo grupo físico"},
         items=[item(category="MACHO", quality="A", quantity=2)])
    occ = Occupation.objects.get(pen=f["pm"])
    one, _ = create(f, items=[line(units=2)])
    two, _ = create(f, items=[line(units=2)])
    for order in [one, two]:
        act(f, "CONFIRM", actor=f["worker"], order=order)
        pay(f, order)
    prepare(f, one, occ=occ)
    c = command(f["worker"], "SELECT", two, shed_ids=[str(f["g1"].id)], items=[
        {"line_id": str(two.lines.get().id), "occupation_id": str(occ.id), "category": "MACHO", "quality": "A", "quantity": 2},
    ])
    result, status = dispatch(f["worker"], c)
    assert status == 409 and result["error"]["code"] == "SELECTION_UNAVAILABLE"
    assert DispatchSelection.objects.filter(preparation=one.preparation).count() == 1
    assert total(f["pm"]) == 2


def test_multi_shed_origin_consent_and_trace_keeps_each_lot(market):
    f = market
    g = Shed.objects.create(center=f["can"], code="G9", name="Segundo galpón de prueba")
    p = Pen.objects.create(shed=g, code="CAN-G9-P01", purpose="RECRIA_MACHOS", capacity=20)
    second = User.objects.create_user(username="second-origin", name="Responsable segundo origen")
    a = assign(second, "GALPONERO", f["can"])
    ShedGrant.objects.create(assignment=a, shed=g)
    send(second, "OPEN", pen_id=str(p.id), lot={"provenance": "Grupo de otro origen"},
         items=[item(category="MACHO", quality="A", quantity=2)])
    occ = Occupation.objects.get(pen=p)
    order, _ = create(f, mode="PUNTO", items=[line(units=2)])
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    act(f, "DRIVER", order=order, driver_id=str(f["driver"].id))
    for actor, source, shed in [(f["worker"], f["occupation"], f["g1"]), (second, occ, g)]:
        act(f, "SELECT", actor=actor, order=order, shed_ids=[str(shed.id)], items=[
            {"line_id": str(order.lines.get().id), "occupation_id": str(source.id), "category": "MACHO", "quality": "A", "quantity": 1},
        ])
    origin(f, order)
    act(f, "PICKUP", actor=f["driver"], order=order, preparation_id=str(order.preparation_id),
        round=order.confirmation_round, shed_ids=[])
    refused, status = dispatch(f["worker"], command(f["worker"], "DEPART", order))
    assert status == 409 and refused["error"]["code"] == "ORIGIN_CONFIRMATION_REQUIRED"
    origin(f, order, actor=second, sheds=[g])
    act(f, "DEPART", actor=f["worker"], order=order)
    assert order.dispatch.details.count() == 2
    assert total(f["p1"]) == 27 and total(p) == 1
    assert {d.snapshot["pen"] for d in order.dispatch.details.all()} == {f["p1"].code, p.code}
    data = order_data(f["worker"], order, "GALPONERO")
    assert len(data["dispatch"]["details"]) == 1


def test_paid_reservation_does_not_expire_and_wrong_payment_is_not_saved(market):
    f = market
    order, _ = create(f)
    act(f, "CONFIRM", actor=f["worker"], order=order)
    result, status = dispatch(f["admin"], command(f["admin"], "PAY", order, amount="1.00",
        currency="PEN", method="Efectivo", reference="Mal importe", evidence_id=str(evidence(f).id)))
    assert status == 409 and result["error"]["code"] == "PAYMENT_AMOUNT_MISMATCH"
    assert not SalePayment.objects.exists()
    pay(f, order)
    reserve = order.reservations.get()
    reserve.expires_at = timezone.now() - timedelta(days=1)
    reserve.save()
    assert not expire_one(f["admin"], reserve.id)
    assert order.reservations.get().state == "PAGADA"


def test_availability_proposal_requires_admin_acceptance_then_new_confirmation(market):
    f = market
    order, _ = create(f, items=[line(units=2)])
    act(f, "PROPOSE", actor=f["worker"], order=order, items=[{"line_id": str(order.lines.get().id), "units": 1}])
    assert order.state == "AJUSTE_PENDIENTE" and not order.reservations.exists()
    with pytest.raises(DomainError):
        dispatch(f["worker"], command(f["worker"], "PROPOSAL_REVIEW", order, proposal_id=str(order.proposals.get().id), approve=True))
    act(f, "PROPOSAL_REVIEW", order=order, proposal_id=str(order.proposals.get().id), approve=True)
    assert order.state == "SOLICITADO" and order.total == Decimal("10")
    assert not order.reservations.exists()
    act(f, "CONFIRM", actor=f["worker"], order=order)
    assert order.reservations.get().details.get().quantity == 1


def test_mortality_shortage_notification_paid_cancel_requires_resolution(market):
    f = market
    order, _ = create(f, items=[line(units=8)])
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    prepare(f, order)
    send(f["worker"], "DEATH", items=[item(f["occupation"], category="MACHO", quality="A")], cause="desconocida")
    order.refresh_from_db()
    assert order.shortage and total(f["p1"]) == 27
    assert Notification.objects.filter(type="SALE_SHORTAGE").count() == 1
    assert order_data(f["admin"], order, "ADMIN")["shortage"]
    bad, status = dispatch(f["admin"], command(f["admin"], "CANCEL", order))
    assert status == 409 and bad["error"]["code"] == "PAYMENT_RESOLUTION_REQUIRED"
    act(f, "CANCEL", order=order, payment_treatment="Devolución manual acordada; " + "referencia " * 20)
    assert order.reservations.get().state == "LIBERADA"
    assert order.payment.amount == Decimal("80") and total(f["p1"]) == 27


def test_private_evidence_permissions_validation_and_immutable_history(market, api):
    f = market
    proof = evidence(f)
    for actor in [f["worker"], f["driver"], f["receiver"]]:
        api.force_login(actor)
        assert api.get(f"/api/v1/cuyes/sales/vouchers/{proof.id}").status_code == 403
    with pytest.raises(DomainError):
        upload_evidence(f["admin"], {"id": uuid.uuid4(), "file": SimpleUploadedFile("bad.svg", b"<svg>")})
    order, _ = create(f)
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    with pytest.raises(IntegrityError), transaction.atomic():
        SalePayment.objects.update(amount="1.00")
    api.force_login(f["admin"])
    response = api.get(f"/api/v1/cuyes/sales/vouchers/{proof.id}")
    assert response.status_code == 200 and response["Cache-Control"] == "no-store, private"
    response.close()


def test_wrong_center_shed_driver_and_offline_commands_denied(market, api):
    f = market
    order, _ = create(f, mode="PUNTO")
    with pytest.raises(DomainError):
        dispatch(f["receiver"], command(f["receiver"], "CONFIRM", order))
    api.force_login(f["receiver"])
    assert api.get(f"/api/v1/cuyes/sales/orders/{order.id}?workspace=GALPONERO").status_code == 404
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    with pytest.raises(DomainError):
        dispatch(f["driver"], command(f["driver"], "ARRIVE", order, delivered_to_client=False, physical_responsible="Test", reference="Test"))
    api.force_login(f["worker"])
    c = command(f["worker"], "CONFIRM", order)
    assert api.post("/api/v1/sync/events", {"events": [c]}, format="json").status_code == 422
    assert api.post("/api/v1/cuyes/sales/commands", {**c, "payload": {"reason": "test", "pin": "12345678"}}, format="json").status_code == 422


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_two_orders_compete_for_same_stock(market):
    f = market
    one, _ = create(f, items=[line(units=6)])
    two, _ = create(f, items=[line(units=6)])
    second = User.objects.create_user(username="second-sales-worker")
    a = assign(second, "GALPONERO", f["can"])
    ShedGrant.objects.create(assignment=a, shed=f["g1"])
    commands = [command(f["worker"], "CONFIRM", one), command(second, "CONFIRM", two)]
    barrier = Barrier(2)

    def run(actor_id, c):
        try:
            actor = User.objects.get(pk=actor_id)
            barrier.wait(timeout=10)
            return dispatch(actor, c)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, actor.id, c) for actor, c in zip([f["worker"], second], commands, strict=True)]
        assert sorted(result.result(timeout=30) for result in futures) == [200, 409]
    assert SaleReservation.objects.count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_expiration_races_payment_on_same_reservation(market):
    f = market
    order, _ = create(f)
    act(f, "CONFIRM", actor=f["worker"], order=order)
    reserve = order.reservations.get()
    reserve.expires_at = timezone.now() - timedelta(seconds=1)
    reserve.save()
    second = User.objects.create_user(username="expiry-admin")
    assign(second, "ADMIN")
    c = command(f["admin"], "PAY", order, amount=str(order.total), currency="PEN", method="Efectivo", reference="Test", evidence_id=str(evidence(f).id))
    barrier = Barrier(2)

    def run_pay():
        try:
            actor = User.objects.get(pk=f["admin"].id)
            barrier.wait(timeout=10)
            return dispatch(actor, c)[1]
        finally:
            connections.close_all()

    def run_expire():
        try:
            actor = User.objects.get(pk=second.id)
            barrier.wait(timeout=10)
            return expire_one(actor, reserve.id)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = pool.submit(run_pay), pool.submit(run_expire)
        assert one.result(timeout=30) == 409
        assert two.result(timeout=30)
    assert not SalePayment.objects.exists()
    assert SaleReservation.objects.get().state == "VENCIDA"


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_concurrent_departures_apply_a_single_kardex_discount(market):
    f = market
    order, _ = create(f, mode="PUNTO", items=[line(units=2)])
    act(f, "CONFIRM", actor=f["worker"], order=order)
    pay(f, order)
    act(f, "DRIVER", order=order, driver_id=str(f["driver"].id))
    prepare(f, order)
    origin(f, order)
    act(f, "PICKUP", actor=f["driver"], order=order,
        preparation_id=str(order.preparation_id), round=order.confirmation_round, shed_ids=[])
    second = User.objects.create_user(username="second-dispatcher")
    a = assign(second, "GALPONERO", f["can"])
    ShedGrant.objects.create(assignment=a, shed=f["g1"])
    commands = [command(f["worker"], "DEPART", order), command(second, "DEPART", order)]
    barrier = Barrier(2)

    def run(actor_id, c):
        try:
            actor = User.objects.get(pk=actor_id)
            barrier.wait(timeout=10)
            return dispatch(actor, c)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, actor.id, c) for actor, c in zip([f["worker"], second], commands, strict=True)]
        assert sorted(future.result(timeout=30) for future in futures) == [200, 409]
    assert SaleDispatch.objects.count() == 1
    assert Movement.objects.filter(kind="SALE_DISPATCH").count() == 1
    assert total(f["p1"]) == 26
