import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import IntegrityError, connections, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.audit.models import AuditEntry
from apps.catalog.models import CenterProduct, Location, Product
from apps.common.errors import DomainError
from apps.cuyes.models import (
    Alert,
    AlertPolicy,
    Balance,
    CountDetail,
    CuyLot,
    DailyReport,
    LedgerLine,
    Movement,
    Occupation,
    Pen,
    PhysicalCount,
    Shed,
    ShedGrant,
    Transfer,
)
from apps.cuyes.reports import indicator, pen_data, refresh_alerts
from apps.cuyes.services import configure, total
from apps.notifications.models import Notification
from apps.sync.batch import process, validate_batch
from apps.sync.commands import dispatch
from apps.sync.models import Device
from apps.sync.snapshots import collect, scope_hash
from tests.test_access import assign

pytestmark = pytest.mark.django_db


def command(actor, kind, **payload):
    device = Device.objects.filter(user=actor).first() or Device.objects.create(user=actor, name="Test")
    return {
        "event_id": str(uuid.uuid4()), "entity_id": str(uuid.uuid4()),
        "device_id": str(device.id), "type": f"CUY_{kind}",
        "occurred_at": timezone.now().isoformat(), "depends_on": [],
        "payload": {"date": timezone.localdate().isoformat(), "reason": "Hecho físico comprobado", **payload},
    }


def send(actor, kind, **payload):
    body, status = dispatch(actor, command(actor, kind, **payload))
    assert status == 200, body
    return body["result"]


def item(occ=None, category="MACHO", quantity=1, quality="SIN_CLASIFICAR", pen=None):
    data = {"category": category, "quantity": quantity, "quality": quality}
    if occ:
        data["occupation_id"] = str(occ.id)
    if pen:
        data["pen_id"] = str(pen.id)
    return data


def open_pen(actor, pen, *, males=2, females=5, babies=10, day=None, installed=None):
    data = {"provenance": "Conteo físico real"}
    if installed:
        data["installed_on"] = installed.isoformat()
    c = command(
        actor, "OPEN", pen_id=str(pen.id), lot=data,
        items=[item(category=c, quantity=n) for c, n in [("MACHO", males), ("HEMBRA", females), ("LACTANTE", babies)] if n],
    )
    if day:
        c["payload"]["date"] = day.isoformat()
    body, status = dispatch(actor, c)
    assert status == 200, body
    return Occupation.objects.get(pen=pen), c


@pytest.fixture
def farm(user):
    for code in Role.Code.values:
        Role.objects.get_or_create(code=code)
    assign(user, "ADMIN")
    can = Location.objects.create(code="CAN", name="Canchán", kind="CENTRO")
    kot = Location.objects.create(code="KOT", name="Kotosh", kind="CENTRO")
    for center in [can, kot]:
        configure(user, {"resource": "enable", "id": uuid.uuid4(), "center_id": center.id, "active": True, "reason": "Piloto"})
    g1 = Shed.objects.create(center=can, code="G1", name="Canchán 1")
    g2 = Shed.objects.create(center=kot, code="G1", name="Kotosh 1")
    g3 = Shed.objects.create(center=kot, code="G2", name="Kotosh 2")
    p1 = Pen.objects.create(shed=g1, code="CAN-G1-P01", purpose="MATERNIDAD", capacity=100)
    pm = Pen.objects.create(shed=g1, code="CAN-G1-P02", purpose="RECRIA_MACHOS", capacity=40)
    pf = Pen.objects.create(shed=g1, code="CAN-G1-P03", purpose="RECRIA_HEMBRAS", capacity=40)
    p2 = Pen.objects.create(shed=g2, code="KOT-G1-P01", purpose="MATERNIDAD", capacity=100)
    p3 = Pen.objects.create(shed=g3, code="KOT-G2-P01", purpose="MATERNIDAD", capacity=100)
    worker = User.objects.create_user(username="galponero", name="Galponero")
    receiver = User.objects.create_user(username="receptor-cuy", name="Receptor")
    a1 = assign(worker, "GALPONERO", can)
    a2 = assign(receiver, "GALPONERO", kot)
    grant = ShedGrant.objects.create(assignment=a1, shed=g1)
    ShedGrant.objects.create(assignment=a2, shed=g2)
    return dict(admin=user, worker=worker, receiver=receiver, p1=p1, pm=pm, pf=pf, p2=p2, p3=p3, g1=g1, g2=g2, g3=g3, can=can, kot=kot, grant=grant)


def test_role_configuration_reuses_catalog_and_no_fake_stock(farm):
    f = farm
    configure(f["admin"], {"resource": "enable", "id": uuid.uuid4(), "center_id": f["can"].id, "active": True, "reason": "Reintento"})
    assert Product.objects.filter(code="CUYES").count() == 1
    assert CenterProduct.objects.filter(product__code="CUYES").count() == 2
    assert not Balance.objects.exists()
    assert not Movement.objects.exists()
    assert not Location.objects.exclude(code__in=["CAN", "KOT"]).exists()
    a = assign(f["worker"], "GALPONERO", f["kot"])
    with pytest.raises(DomainError, match="centro"):
        configure(f["admin"], dict(resource="grant", id=uuid.uuid4(), assignment_id=a.id, shed_id=f["g1"].id, active=True, reason="Error"))


def test_physical_opening_keeps_mixed_groups_separate_and_known_age(farm):
    f = farm
    day = timezone.localdate()
    send(f["worker"], "OPEN", pen_id=str(f["p1"].id), groups=[
        {"lot": {"provenance": "Reproductores A", "installed_on": (day - timedelta(days=30)).isoformat()},
         "items": [item(category="HEMBRA", quantity=5, quality="A")]},
        {"lot": {"provenance": "Lactantes B", "born_from": (day - timedelta(days=12)).isoformat(),
                 "born_until": (day - timedelta(days=10)).isoformat()},
         "items": [item(category="LACTANTE", quantity=4)]},
    ])
    assert total(f["p1"]) == 9
    assert Occupation.objects.filter(pen=f["p1"]).count() == 2
    assert PhysicalCount.objects.filter(opening=True).count() == 1
    lots = {o["lot"]["provenance"]: o["lot"] for o in pen_data(f["p1"])["occupations"]}
    assert lots["Reproductores A"]["reproductive_days"] == 30
    assert lots["Lactantes B"]["age_days_min"] == 10
    assert lots["Lactantes B"]["age_days_max"] == 12


def test_api_isolation_sheds_dual_role_and_offline_revocation(api, farm):
    f = farm
    assign(f["worker"], "PRODUCCION", f["can"])
    api.force_login(f["worker"])
    assert len(api.get("/api/v1/cuyes/pens").json()["results"]) == 3
    assert api.get(f"/api/v1/cuyes/pens/{f['p2'].id}").status_code == 404
    api.force_login(f["receiver"])
    rows = api.get("/api/v1/cuyes/pens").json()["results"]
    assert [p["id"] for p in rows] == [str(f["p2"].id)]
    assert api.get(f"/api/v1/cuyes/pens/{f['p3'].id}").status_code == 404
    before = collect(f["worker"])
    old_scope = scope_hash(f["worker"])
    assert any(v["entity_type"] == "cuy_pen" for v in before.values())
    f["grant"].active = False
    f["grant"].save()
    after = collect(f["worker"])
    assert scope_hash(f["worker"]) != old_scope
    assert not any(v["entity_type"] == "cuy_pen" for v in after.values())
    assert any(before[k]["entity_type"] == "cuy_pen" for k in before.keys() - after.keys())


def test_opening_replay_and_immutable_kardex(farm):
    f = farm
    occ, c = open_pen(f["worker"], f["p1"])
    initial, status = dispatch(f["worker"], c)
    assert status == 200
    assert dispatch(f["worker"], c) == (initial, status)
    assert total(f["p1"]) == 17
    assert PhysicalCount.objects.filter(opening=True).count() == 1
    assert Movement.objects.count() == 1
    assert CuyLot.objects.count() == 1
    for model in [Movement, LedgerLine, CuyLot, CountDetail]:
        with pytest.raises(IntegrityError), transaction.atomic():
            model.objects.all().delete()
    assert AuditEntry.objects.filter(entity_type="cuy_movement").exists()
    with pytest.raises(DomainError):
        changed = {**c, "payload": {**c["payload"], "reason": "Otra intención"}}
        dispatch(f["worker"], changed)
    assert occ.pen_id == f["p1"].id


def test_birth_stillborn_mortality_and_overcapacity(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    send(f["worker"], "BIRTH", occupation_id=str(occ.id), live=3, stillborn=2)
    assert total(f["p1"]) == 20
    assert CuyLot.objects.filter(parent=occ.lot, born_from=timezone.localdate()).exists()
    send(f["worker"], "BIRTH", occupation_id=str(occ.id), live=0, stillborn=4)
    assert total(f["p1"]) == 20
    response, status = dispatch(f["worker"], command(f["worker"], "DEATH", items=[item(occ, quantity=3)]))
    assert status == 409 and response["error"]["code"] == "INSUFFICIENT_BALANCE"
    assert total(f["p1"]) == 20
    send(f["worker"], "DEATH", items=[item(occ)], cause="desconocida")
    assert total(f["p1"]) == 19
    f["p1"].capacity = 18
    f["p1"].save()
    send(f["worker"], "BIRTH", occupation_id=str(occ.id), live=2, stillborn=0)
    assert total(f["p1"]) == 21
    assert Alert.objects.filter(kind="CAPACITY").count() == 1
    assert Notification.objects.filter(type="CUY_ALERT").count() == 1


def test_weaning_distributed_and_atomic_failure(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    data = dict(occupation_id=str(occ.id), quantity=7, quality="SIN_CLASIFICAR",
                destinations=[item(category="MACHO", quality="A", quantity=3, pen=f["pm"]),
                              item(category="HEMBRA", quality="B", quantity=4, pen=f["pf"])])
    f["pf"].capacity = 3
    f["pf"].save()
    body, status = dispatch(f["worker"], command(f["worker"], "WEAN", **data))
    assert status == 409 and body["error"]["code"] == "CAPACITY_EXCEEDED"
    assert total(f["p1"]) == 17 and total(f["pm"]) == 0
    assert CuyLot.objects.count() == 1
    f["pf"].capacity = 40
    f["pf"].save()
    send(f["worker"], "WEAN", **data)
    assert total(f["p1"]) == 10 and total(f["pm"]) == 3 and total(f["pf"]) == 4
    lots = CuyLot.objects.filter(parent=occ.lot)
    assert lots.count() == 1 and lots.get().source_occupation_id == occ.id
    assert indicator(f["p1"], timezone.localdate(), timezone.localdate())["weaned"] == 7


def test_weaning_rejects_unauthorized_other_kotosh_shed(farm):
    f = farm
    occ, _ = open_pen(f["receiver"], f["p2"])
    body, status = dispatch(f["receiver"], command(f["receiver"], "WEAN",
        occupation_id=str(occ.id), quantity=1,
        destinations=[item(category="MACHO", quality="B", pen=f["p3"])],
    ))
    assert status == 403
    assert total(f["p2"]) == 17 and total(f["p3"]) == 0


def test_cross_center_transit_duplicate_reception_and_redirection(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    result = send(f["worker"], "DISPATCH", source_id=str(f["p1"].id), destination_id=str(f["p2"].id), items=[item(occ, "HEMBRA", 2)])
    transfer = Transfer.objects.get(pk=result["movement_id"])
    assert total(f["p1"]) == 15 and total(f["p2"]) == 0
    assert transfer.state == "EN_TRANSITO"
    with pytest.raises(DomainError):
        dispatch(f["worker"], command(f["worker"], "RECEIVE", transfer_id=str(transfer.id)))
    f["p2"].active = False
    f["p2"].save()
    with pytest.raises(DomainError):
        dispatch(f["receiver"], command(f["receiver"], "RECEIVE", transfer_id=str(transfer.id)))
    send(f["admin"], "REDIRECT", transfer_id=str(transfer.id), destination_id=str(f["p3"].id))
    with pytest.raises(DomainError):
        dispatch(f["receiver"], command(f["receiver"], "RECEIVE", transfer_id=str(transfer.id)))
    a = f["receiver"].assignments.get(role_id="GALPONERO")
    ShedGrant.objects.create(assignment=a, shed=f["g3"])
    c = command(f["receiver"], "RECEIVE", transfer_id=str(transfer.id))
    first = dispatch(f["receiver"], c)
    assert first[1] == 200 and dispatch(f["receiver"], c) == first
    body, status = dispatch(f["receiver"], command(f["receiver"], "RECEIVE", transfer_id=str(transfer.id)))
    assert status == 409 and body["error"]["code"] == "ALREADY_RECEIVED"
    assert total(f["p3"]) == 2
    transfer.refresh_from_db()
    assert transfer.dispatched_by_id == f["worker"].id and transfer.received_by_id == f["receiver"].id


def test_receive_rechecks_capacity_and_keeps_transit(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    t = send(f["worker"], "DISPATCH", source_id=str(f["p1"].id), destination_id=str(f["p2"].id), items=[item(occ, "HEMBRA", 2)])
    f["p2"].capacity = 1
    f["p2"].save()
    body, status = dispatch(f["receiver"], command(f["receiver"], "RECEIVE", transfer_id=t["movement_id"]))
    assert status == 409 and body["error"]["code"] == "CAPACITY_EXCEEDED"
    assert Transfer.objects.get().state == "EN_TRANSITO" and total(f["p2"]) == 0


def test_monthly_count_preserves_later_movements(farm):
    f = farm
    yesterday = timezone.localdate() - timedelta(days=1)
    occ, _ = open_pen(f["worker"], f["p1"], day=yesterday)
    counted = send(f["worker"], "COUNT", pen_id=str(f["p1"].id), date=yesterday.isoformat(), items=[
        item(occ, "MACHO", 1), item(occ, "HEMBRA", 5), item(occ, "LACTANTE", 10),
    ])
    assert total(f["p1"]) == 17
    send(f["worker"], "BIRTH", occupation_id=str(occ.id), live=3)
    assert total(f["p1"]) == 20
    send(f["admin"], "REVIEW", count_id=counted["count_id"], approve=True)
    assert total(f["p1"]) == 19
    count = PhysicalCount.objects.get(pk=counted["count_id"])
    assert count.state == "APLICADO"
    assert count.details.get(category="MACHO").expected == 2
    assert Notification.objects.filter(type="CUY_DIFFERENCE").count() == 1


def test_incoherent_adjustment_retains_original_count(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    counted = send(f["worker"], "COUNT", pen_id=str(f["p1"].id), items=[
        item(occ, "MACHO", 0), item(occ, "HEMBRA", 5), item(occ, "LACTANTE", 10),
    ])
    send(f["worker"], "DEATH", items=[item(occ, quantity=1)])
    body, status = dispatch(f["admin"], command(f["admin"], "REVIEW", count_id=counted["count_id"], approve=True))
    assert status == 409 and body["error"]["code"] == "INSUFFICIENT_BALANCE"
    assert PhysicalCount.objects.get(pk=counted["count_id"]).state == "PENDIENTE"
    assert total(f["p1"]) == 16


def test_zero_daily_close_late_move_and_audited_reopen(farm):
    f = farm
    send(f["worker"], "CLOSE", shed_id=str(f["g1"].id))
    assert DailyReport.objects.get().state == "CERRADO"
    body, status = dispatch(f["worker"], command(f["worker"], "OPEN", pen_id=str(f["p1"].id),
        lot={"provenance": "Físico"}, items=[item(quantity=1)]))
    assert status == 409 and body["error"]["code"] == "DAY_CLOSED"
    send(f["admin"], "REOPEN", shed_id=str(f["g1"].id))
    open_pen(f["worker"], f["p1"])
    send(f["worker"], "CLOSE", shed_id=str(f["g1"].id))
    assert DailyReport.objects.count() == 1
    assert DailyReport.objects.get().revisions.count() == 3


def test_offline_same_uuid_revocation_and_balance_conflict(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    c = command(f["worker"], "DEATH", items=[item(occ)])
    events = validate_batch({"events": [c]})
    result = process(f["worker"], events)
    assert result["results"][0]["status"] == "APLICADA"
    assert process(f["worker"], events)["results"][0]["status"] == "APLICADA"
    assert total(f["p1"]) == 16
    waiting = command(f["worker"], "DEATH", items=[item(occ, quantity=2)])
    outcome = process(f["worker"], validate_batch({"events": [waiting]}))
    assert outcome["results"][0]["error"]["code"] == "INSUFFICIENT_BALANCE"
    f["grant"].active = False
    f["grant"].save()
    outcome = process(f["worker"], events)
    assert outcome["results"][0]["http_status"] == 403
    assert outcome["results"][0]["persisted"] is False
    assert total(f["p1"]) == 16


@pytest.mark.django_db(transaction=True)
def test_snapshot_protocol_removes_revoked_shed_and_rejects_partial_pages(farm):
    from apps.sync.snapshots import page

    f = farm
    actor = f["worker"]
    device = Device.objects.create(user=actor, name="Offline autorizado")
    baseline = page(actor, device.id, {"limit": 200})
    assert baseline["cursor"]
    cuy_ids = {row["id"] for row in baseline["results"] if row["entity_type"] == "cuy_pen"}
    assert cuy_ids == {str(f[key].id) for key in ["p1", "pm", "pf"]}
    partial = page(actor, device.id, {"limit": 1})
    assert partial["next_page"]
    f["grant"].active = False
    f["grant"].save()
    with pytest.raises(DomainError, match="Cambió"):
        page(actor, device.id, {"limit": 1, "page": partial["next_page"]})
    delta = page(actor, device.id, {"limit": 200, "cursor": baseline["cursor"]}, changes=True)
    deleted = {row["id"] for row in delta["results"] if row["entity_type"] == "cuy_pen" and row["deleted"]}
    assert deleted == cuy_ids
    assert not any(row["entity_type"] == "cuy_pen" and not row["deleted"] for row in delta["results"])


def test_quality_c_admin_and_compensation(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    with pytest.raises(DomainError):
        dispatch(f["worker"], command(f["worker"], "RECLASS", items=[item(occ)], new_quality="C"))
    moved = send(f["admin"], "RECLASS", items=[item(occ)], new_quality="C")
    assert total(f["p1"]) == 17
    assert Balance.objects.get(occupation=occ, category="MACHO", quality="C").quantity == 1
    send(f["admin"], "COMPENSATE", movement_id=moved["movement_id"])
    assert Balance.objects.get(occupation=occ, category="MACHO", quality="C").quantity == 0
    assert total(f["p1"]) == 17


def test_female_weighted_average_unknown_age_alert_dedup(farm):
    f = farm
    today = timezone.localdate()
    start = today - timedelta(days=9)
    occ, _ = open_pen(f["worker"], f["p1"], day=start, installed=start - timedelta(days=450))
    send(f["worker"], "DEATH", date=(start + timedelta(days=5)).isoformat(), items=[item(occ, "HEMBRA", 2)])
    metric = indicator(f["p1"], start, today)
    assert metric["average_females"] == 4
    assert metric["weaned_per_female"] == 0
    assert pen_data(f["p1"])["occupations"][0]["lot"]["age_days_min"] is None
    AlertPolicy.objects.update_or_create(center=f["can"], defaults={"reproductive_months": 13})
    with transaction.atomic():
        refresh_alerts(today)
        refresh_alerts(today)
    assert Alert.objects.filter(kind="REPRODUCTIVE_AGE").count() == 1
    assert not Movement.objects.filter(kind="RECLASS").exists()
    assert indicator(f["p2"], start, today)["status"] == "datos insuficientes"


def test_api_journey_config_grant_open_birth_and_close(api, farm):
    f = farm
    path = "/api/v1/cuyes/config"
    result = api.post(path, dict(resource="shed", id=str(uuid.uuid4()), center_id=str(f["can"].id),
                                code="G4", name="Galpón nuevo", active=True, reason="Configuración real"), format="json")
    assert result.status_code == 200, result.data
    shed_id = result.json()["id"]
    result = api.post(path, dict(resource="pen", id=str(uuid.uuid4()), shed_id=shed_id,
                                code="CAN-G4-P01", capacity=100, purpose="MATERNIDAD",
                                active=True, reason="Configuración real"), format="json")
    assert result.status_code == 200, result.data
    pen = Pen.objects.get(pk=result.json()["id"])
    assignment = f["worker"].assignments.get(role_id="GALPONERO")
    result = api.post(path, dict(resource="grant", id=str(uuid.uuid4()), shed_id=shed_id,
                                assignment_id=str(assignment.id), active=True, reason="Responsable asignado"), format="json")
    assert result.status_code == 200, result.data
    api.force_login(f["worker"])
    c = command(f["worker"], "OPEN", pen_id=str(pen.id), lot={"provenance": "Conteo real"},
                items=[item(category="HEMBRA", quantity=5)])
    result = api.post("/api/v1/cuyes/commands", c, format="json")
    assert result.status_code == 200, result.data
    occ = Occupation.objects.get(pen=pen)
    c = command(f["worker"], "BIRTH", occupation_id=str(occ.id), live=3, stillborn=1)
    result = api.post("/api/v1/sync/events", {"events": [c]}, format="json")
    assert result.status_code == 200, result.data
    assert result.json()["results"][0]["status"] == "APLICADA"
    assert api.get(f"/api/v1/cuyes/pens/{pen.id}").json()["population"] == 8
    result = api.post("/api/v1/cuyes/commands", command(f["worker"], "CLOSE", shed_id=shed_id), format="json")
    assert result.status_code == 200, result.data
    c = command(f["worker"], "DEATH", items=[item(occ, "HEMBRA")])
    result = api.post("/api/v1/sync/events", {"events": [c]}, format="json")
    assert result.json()["results"][0]["error"]["code"] == "DAY_CLOSED"
    result = api.post("/api/v1/cuyes/commands", {**c, "payload": {**c["payload"], "extra": 1}}, format="json")
    assert result.status_code == 422
    assert api.get("/api/v1/cuyes/pens?extra=1").status_code == 422
    assert api.get("/api/v1/cuyes/config").status_code == 403


def test_invalid_dates_purpose_immediate_cross_center_and_backdated_count(farm):
    f = farm
    yesterday = timezone.localdate() - timedelta(days=1)
    occ, _ = open_pen(f["worker"], f["p1"], day=yesterday)
    cases = [
        ("MOVE", dict(source_id=str(f["p1"].id), destination_id=str(f["pm"].id), items=[item(occ, "HEMBRA")])),
        ("MOVE", dict(source_id=str(f["p1"].id), destination_id=str(f["p2"].id), items=[item(occ)])),
        ("BIRTH", dict(occupation_id=str(occ.id), live=1, date=(yesterday - timedelta(days=1)).isoformat())),
        ("DEATH", dict(items=[item(occ)], date=(timezone.localdate() + timedelta(days=1)).isoformat())),
    ]
    for kind, payload in cases:
        result, status = dispatch(f["worker"], command(f["worker"], kind, **payload))
        assert status in [409, 422], result
    assert total(f["p1"]) == 17
    send(f["worker"], "COUNT", pen_id=str(f["p1"].id), items=[item(occ, "MACHO", 2), item(occ, "HEMBRA", 5), item(occ, "LACTANTE", 10)])
    result, status = dispatch(f["worker"], command(f["worker"], "DEATH", date=yesterday.isoformat(), items=[item(occ)]))
    assert status == 409 and result["error"]["code"] == "COUNT_CUT_LOCKED"


def test_count_and_birth_overcapacity_notifies_once_and_cannot_change_purpose(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    f["p1"].capacity = 17
    f["p1"].save()
    send(f["worker"], "BIRTH", occupation_id=str(occ.id), live=1)
    send(f["worker"], "BIRTH", occupation_id=str(occ.id), live=1)
    assert total(f["p1"]) == 19
    assert Alert.objects.filter(kind="CAPACITY").count() == 1
    assert Notification.objects.filter(type="CUY_ALERT").count() == 1
    with pytest.raises(DomainError):
        configure(f["admin"], dict(resource="pen", id=f["p1"].id, shed_id=f["g1"].id,
            code=f["p1"].code, capacity=100, purpose="RECRIA_MACHOS", active=True, reason="No compatible"))
    assert Pen.objects.get(pk=f["p1"].id).purpose == "MATERNIDAD"


def test_shared_movement_read_does_not_leak_revoked_shed_payload(api, farm):
    f = farm
    actor = f["receiver"]
    assignment = actor.assignments.get(role_id="GALPONERO")
    grant = ShedGrant.objects.create(assignment=assignment, shed=f["g3"])
    one, _ = open_pen(actor, f["p2"])
    two, _ = open_pen(actor, f["p3"])
    movement = send(actor, "DEATH", items=[item(one), item(two)])
    grant.active = False
    grant.save()
    api.force_login(actor)
    result = api.get("/api/v1/cuyes/kardex").json()
    row = next(m for m in result["results"] if m["id"] == movement["movement_id"])
    assert len(row["lines"]) == 1
    assert row["lines"][0]["snapshot"]["pen_id"] == str(f["p2"].id)
    assert "items" not in row["metadata"]
    assert str(two.id) not in str(row)


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_close_serializes_with_other_accounts_birth(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    second = User.objects.create_user(username="closing-worker")
    a = assign(second, "GALPONERO", f["can"])
    ShedGrant.objects.create(assignment=a, shed=f["g1"])
    birth = command(f["worker"], "BIRTH", occupation_id=str(occ.id), live=2)
    close = command(second, "CLOSE", shed_id=str(f["g1"].id))
    barrier = Barrier(2)

    def run(actor_id, c):
        try:
            actor = User.objects.get(pk=actor_id)
            barrier.wait(timeout=10)
            return dispatch(actor, c)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(run, f["worker"].id, birth)
        two = pool.submit(run, second.id, close)
        born, closed = one.result(timeout=30), two.result(timeout=30)
    assert closed[1] == 200
    assert born[1] in [200, 409]
    assert total(f["p1"]) == (19 if born[1] == 200 else 17)
    assert DailyReport.objects.get().state == "CERRADO"


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
def test_concurrent_receivers_consume_transit_once(farm):
    f = farm
    occ, _ = open_pen(f["worker"], f["p1"])
    t = send(f["worker"], "DISPATCH", source_id=str(f["p1"].id), destination_id=str(f["p2"].id), items=[item(occ)])
    second = User.objects.create_user(username="second-receiver")
    a = assign(second, "GALPONERO", f["kot"])
    ShedGrant.objects.create(assignment=a, shed=f["g2"])
    commands = [command(actor, "RECEIVE", transfer_id=t["movement_id"]) for actor in [f["receiver"], second]]
    barrier = Barrier(2)

    def run(actor_id, c):
        try:
            actor = User.objects.get(pk=actor_id)
            barrier.wait(timeout=10)
            return dispatch(actor, c)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, actor.id, c) for actor, c in zip([f["receiver"], second], commands, strict=True)]
        assert sorted(future.result(timeout=30) for future in futures) == [200, 409]
    assert total(f["p2"]) == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.concurrency
@pytest.mark.parametrize("capacity_race", [False, True])
def test_concurrent_moves_protect_balance_and_total_pen_capacity(farm, capacity_race):
    f = farm
    first = f["worker"]
    second = User.objects.create_user(username="second-worker")
    a = assign(second, "GALPONERO", f["can"])
    ShedGrant.objects.create(assignment=a, shed=f["g1"])
    occ, _ = open_pen(first, f["p1"])
    if capacity_race:
        f["pm"].capacity = 1
        f["pm"].save()
        # Two distinct occupations compete for one pen's capacity.
        send(first, "BIRTH", occupation_id=str(occ.id), live=1)
        baby = Occupation.objects.filter(lot__parent=occ.lot).first()
        send(first, "WEAN", occupation_id=str(baby.id), quantity=1,
             destinations=[item(category="MACHO", quality="B", pen=f["pm"])])
        # Move that animal back to create a distinct male occupation at origin.
        other_occ = Occupation.objects.get(pen=f["pm"])
        send(first, "MOVE", source_id=str(f["pm"].id), destination_id=str(f["p1"].id), items=[item(other_occ, quality="B")])
        second_occ = Occupation.objects.get(pen=f["p1"], lot=other_occ.lot)
        one = command(first, "MOVE", source_id=str(f["p1"].id), destination_id=str(f["pm"].id), items=[item(occ)])
        two = command(second, "MOVE", source_id=str(f["p1"].id), destination_id=str(f["pm"].id), items=[item(second_occ, quality="B")])
    else:
        one = command(first, "MOVE", source_id=str(f["p1"].id), destination_id=str(f["pm"].id), items=[item(occ, quantity=2)])
        two = command(second, "MOVE", source_id=str(f["p1"].id), destination_id=str(f["pm"].id), items=[item(occ, quantity=2)])
    barrier = Barrier(2)

    def run(actor_id, c):
        try:
            actor = User.objects.get(pk=actor_id)
            barrier.wait(timeout=10)
            return dispatch(actor, c)[1]
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, first.id, one), pool.submit(run, second.id, two)]
        statuses = sorted(f.result(timeout=30) for f in futures)
    assert statuses == [200, 409]
    assert total(f["pm"]) == (1 if capacity_race else 2)
    assert not Balance.objects.filter(quantity__lt=0).exists()
    assert (LedgerLine.objects.aggregate(n=Sum("delta"))["n"] or 0) == Balance.objects.aggregate(n=Sum("quantity"))["n"]
