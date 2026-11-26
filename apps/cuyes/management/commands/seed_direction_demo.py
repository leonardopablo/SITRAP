import os
import random
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.access import active_assignments
from apps.accounts.models import RoleAssignment
from apps.catalog.models import (
    Animal,
    AnimalStay,
    CenterProduct,
    Location,
    Presentation,
    Product,
    Species,
    Turn,
    Unit,
)
from apps.cuyes.models import Balance, Occupation, Pen, SaleOrder, SaleReservation, Shed, ShedGrant
from apps.cuyes.sales_private import deliver_with_pin, generate_pin, upload_evidence
from apps.cuyes.sales_services import expire_one
from apps.sync.commands import dispatch
from apps.sync.models import Device
from apps.traceability.models import Transfer

START = date(2026, 1, 1)
REASON = "DEMO · operación ficticia"
PRESERVE = {"cuyes_alertpolicy"}
RESET_EXACT = {"audit_auditentry", "catalog_animal", "catalog_animalstay", "django_session", "accounts_loginbucket"}
RESET_PREFIXES = ("cuyes_", "milk_", "production_", "traceability_", "notifications_", "sync_")


def stamp(day, hour=8):
    return datetime.combine(day, time(hour), timezone.get_default_timezone())


def numbers(total, count, rng):
    base, remainder = divmod(total, count)
    result = [base + (i < remainder) for i in range(count)]
    for i in range(count):
        j = (i + 1) % count
        change = rng.randint(-6, 6)
        result[i] += change
        result[j] -= change
    return result


def bucket(category, quality, quantity, *, occ=None, pen=None):
    result = dict(category=category, quality=quality, quantity=quantity)
    if occ:
        result["occupation_id"] = str(occ.pk)
    if pen:
        result["pen_id"] = str(pen.pk)
    return result


class Demo:
    def __init__(self, end):
        self.end = end
        self.rng = random.Random(20260101)
        self.devices = {}

    @staticmethod
    def assignment(role, center=None):
        now = timezone.now()
        rows = RoleAssignment.objects.filter(role_id=role, location=center,
                                              user__is_active=True, user__password_change_required=False)
        for row in rows.select_related("user").order_by("starts_at"):
            if row.starts_at <= now and (row.ends_at is None or row.ends_at > now):
                return row
        raise CommandError(f"Falta cuenta lista con rol {role} en {center.name if center else 'ámbito global'}.")

    def send(self, actor, kind, day, *, entity=None, version=None, hour=8, **data):
        if actor.id not in self.devices:
            self.devices[actor.id] = Device.objects.create(user=actor, name="SITRAP demostración").id
        if kind.startswith("CUY_"):
            data.update(date=day.isoformat(), reason=REASON)
        if kind.startswith("SALE_"):
            data["reason"] = REASON
        envelope = dict(event_id=str(uuid4()), entity_id=str(entity or uuid4()),
                        device_id=str(self.devices[actor.id]), type=kind,
                        occurred_at=stamp(day, hour).isoformat(), depends_on=[], payload=data)
        if version is not None:
            envelope["expected_version"] = version
        with patch.object(timezone, "now", return_value=stamp(day, hour)):
            body, status = dispatch(actor, envelope)
        if status != 200 or body["status"] != "APLICADA":
            raise CommandError(f"{day} {kind}: {body.get('error')}")
        return body["result"]

    def milk(self, center, point, producer, driver, receiver):
        unit, _ = Unit.objects.get_or_create(code="L", defaults={"name": "Litros"})
        product = (Product.objects.filter(code="LECHE").first() or
                   Product.objects.filter(unit=unit, name__icontains="leche").first())
        if not product:
            product = Product.objects.create(code="LECHE", name="Leche", unit=unit)
        CenterProduct.objects.filter(product__unit=unit, center__kind="CENTRO").exclude(center=center).update(enabled=False)
        CenterProduct.objects.update_or_create(center=center, product=product, defaults={"enabled": True})
        package = Presentation.objects.create(product=product, name="Litro · demostración",
                                              content_base=Decimal("1"), allows_fraction=False)
        species, _ = Species.objects.get_or_create(code="BOVINO", defaults={"name": "Bovino"})
        turn = Turn.objects.filter(active=True).first() or Turn.objects.create(code="AM", name="Mañana")
        cows = [Animal.objects.create(code=f"KOT-V{i:03}", name=f"Vaca {i:02} · demo",
                                      species=species, sex="HEMBRA") for i in range(1, 13)]
        AnimalStay.objects.bulk_create([AnimalStay(animal=c, center=center, starts_on=START) for c in cows])
        for i in range(0, (self.end - START).days + 1, 3):
            day = START + timedelta(days=i)
            milking, production, ver, lot = [uuid4() for _ in range(4)]
            details = [dict(animal_id=str(c.id), liters=f"{Decimal((134 if j < 5 else 61) + self.rng.randint(-23, 23) + (i % 31) // 3) / 10:.3f}")
                       for j, c in enumerate(cows)]
            self.send(producer, "MILKING_CREATE", day, entity=milking, production_id=str(production),
                      version_id=str(ver), center_id=str(center.id), product_id=str(product.id),
                      **{"date": day.isoformat()}, turn_id=str(turn.id), details=details)
            self.send(producer, "MILKING_CONFIRM", day, entity=milking, version=1, version_id=str(ver), lot_id=str(lot))
            if i % 9:
                continue
            transfer, document = uuid4(), uuid4()
            self.send(producer, "TRANSFER_CREATE", day, entity=transfer, hour=9, version_id=str(document),
                      line_id=str(uuid4()), lot_id=str(lot), presentation_id=str(package.id),
                      units=str(int(sum(Decimal(row["liters"]) for row in details)) - 2),
                      destination_id=str(point.id), driver_id=str(driver.id), receiver_id=str(receiver.id))
            self.send(producer, "TRANSFER_SEND", day, entity=transfer, hour=10, version=1, version_id=str(document))
            if (self.end - day).days < 2:
                continue
            self.send(driver, "TRANSFER_PICKUP", day, entity=transfer, hour=11, version=2, version_id=str(document))
            if (self.end - day).days > 3:
                current = Transfer.objects.get(pk=transfer)
                self.send(receiver, "TRANSFER_RECEIVE", day, entity=transfer, hour=13,
                          version=current.lock_version, version_id=str(document))

    def make_pens(self, shed, actor, target, count):
        purposes = ["MATERNIDAD", "RECRIA_MACHOS", "RECRIA_HEMBRAS", "ACABADO"]
        groups = {purpose: [] for purpose in purposes}
        for i, n in enumerate(numbers(target, count, self.rng)):
            purpose = purposes[i % 4]
            pen = Pen.objects.create(shed=shed, code=f"{shed.code}-P{i + 1:03}", capacity=48, purpose=purpose)
            if purpose == "MATERNIDAD":
                items = [bucket("MACHO", "A", max(2, n // 7)), bucket("HEMBRA", "A", n - max(2, n // 7))]
            elif purpose == "ACABADO":
                items = [bucket("MACHO", "B", n // 2), bucket("HEMBRA", "B", n - n // 2)]
            else:
                items = [bucket("MACHO" if purpose == "RECRIA_MACHOS" else "HEMBRA", "A", n)]
            self.send(actor, "CUY_OPEN", START, pen_id=str(pen.id), items=items,
                      lot=dict(provenance="DEMO · Grupo de apertura", born_from="2025-09-01",
                               born_until="2025-10-15"))
            groups[purpose].append(Occupation.objects.get(pen=pen))
        return groups

    def sale(self, day, admin, worker, driver, center, point, shed, mode, sources, *, expire=False, later=False):
        order_id = uuid4()
        lines = [dict(id=str(uuid4()), kind="UNIDAD", units=n, unit_price="25.00", category=c, quality=q)
                 for occ, c, q, n in sources]
        self.send(admin, "SALE_CREATE", day, entity=order_id, hour=9, center_id=str(center.id), mode=mode,
                  client_name=f"Cliente ficticio DE-{day:%m%d}-{shed.code}", items=lines,
                  **({"point_id": str(point.id)} if mode == "PUNTO" else {}))
        order = SaleOrder.objects.get(pk=order_id)

        def step(actor, kind, hour, **data):
            order.refresh_from_db()
            self.send(actor, f"SALE_{kind}", day, entity=order.id, version=order.version, hour=hour, **data)
            order.refresh_from_db()

        step(worker, "CONFIRM", 9)
        if expire:
            reservation = SaleReservation.objects.get(order=order)
            with patch.object(timezone, "now", return_value=reservation.expires_at + timedelta(minutes=1)):
                expire_one(admin, reservation.id)
            return
        with patch.object(timezone, "now", return_value=stamp(day, 10)):
            evidence = upload_evidence(admin, {"id": uuid4(), "file": SimpleUploadedFile(
                "demo.pdf", b"%PDF-1.4\n% DEMOSTRACION: no acredita pago real\n%%EOF", content_type="application/pdf",
            )})
        step(admin, "PAY", 10, amount=str(order.total), currency="PEN", method="Efectivo ficticio",
             reference="DEMO · sin pago real", evidence_id=str(evidence.id))
        if mode == "PUNTO":
            step(admin, "DRIVER", 10, driver_id=str(driver.id))
        step(worker, "SELECT", 11, shed_ids=[str(shed.id)], items=[
            dict(line_id=line["id"], occupation_id=str(occ.id), category=c, quality=q, quantity=n)
            for line, (occ, c, q, n) in zip(lines, sources, strict=True)
        ])
        step(worker, "ORIGIN", 11, preparation_id=str(order.preparation_id), round=order.confirmation_round,
             shed_ids=[str(shed.id)])
        if mode == "PUNTO":
            step(driver, "PICKUP", 12, preparation_id=str(order.preparation_id), round=order.confirmation_round)
            step(worker, "DEPART", 12)
            step(driver, "ARRIVE", 14, delivered_to_client=not later, physical_responsible=driver.name, reference=REASON)
            if later:
                step(admin, "COLLECT", 16, physical_responsible="Encargada ficticia", reference=REASON)
        else:
            with patch.object(timezone, "now", return_value=stamp(day, 13)):
                pin = generate_pin(admin, order.id, dict(expected_version=order.version, reason=REASON))["pin"]
                order.refresh_from_db()
                body, status = deliver_with_pin(worker, order.id, dict(
                    event_id=uuid4(), device_id=self.devices[worker.id], expected_version=order.version,
                    reason=REASON, pin=pin, physical_responsible=worker.name, reference=REASON))
                if status != 200 or not body.get("result", {}).get("pin_valid"):
                    raise CommandError("Falló la entrega simulada con PIN.")

    def cuyes(self, center, groups, shed, admin, worker, driver, point):
        for i, offset in enumerate(range(4, (self.end - START).days - 24, 26)):
            day = START + timedelta(days=offset)
            mother = groups["MATERNIDAD"][i % len(groups["MATERNIDAD"])]
            live = self.rng.randint(7, 12)
            death = self.rng.randint(1, 2)
            weaned = live - death
            self.send(worker, "CUY_BIRTH", day, occupation_id=str(mother.id), live=live, stillborn=i % 3)
            baby = Occupation.objects.get(pen=mother.pen, lot__source_occupation=mother, lot__opened_on=day)
            self.send(worker, "CUY_DEATH", day + timedelta(days=5),
                      items=[bucket("LACTANTE", "SIN_CLASIFICAR", death, occ=baby)], cause="DEMO · causa no determinada")
            m, h = [groups[p][i % len(groups[p])] for p in ("RECRIA_MACHOS", "RECRIA_HEMBRAS")]
            self.send(worker, "CUY_WEAN", day + timedelta(days=18), occupation_id=str(baby.id),
                      quantity=weaned, quality="SIN_CLASIFICAR",
                      destinations=[bucket("MACHO", "A", weaned // 2, pen=m.pen),
                                    bucket("HEMBRA", "A", weaned - weaned // 2, pen=h.pen)])
            sale_sources = []
            for target, sex, quantity in ((m, "MACHO", weaned // 2), (h, "HEMBRA", weaned - weaned // 2)):
                # Sell the oldest remaining cohort, not the just-weaned one.
                remaining = quantity
                for balance in Balance.objects.filter(occupation__pen=target.pen, category=sex, quality="A",
                                                      quantity__gt=0).select_related("occupation").order_by(
                    "occupation__lot__opened_on", "occupation_id",
                ):
                    n = min(remaining, balance.quantity)
                    sale_sources.append((balance.occupation, sex, "A", n))
                    remaining -= n
                    if not remaining:
                        break
                if remaining:
                    raise CommandError("No hay saldo ficticio suficiente para la venta planificada.")
            mode = "PUNTO" if i % 2 else "DIRECTO"
            self.sale(day + timedelta(days=24), admin, worker, driver, center, point, shed, mode,
                      sale_sources, later=i % 4 == 3)
        if self.end >= START + timedelta(days=2):
            self.sale(self.end - timedelta(days=1), admin, worker, driver, center, point, shed, "DIRECTO",
                      [(groups["ACABADO"][0], "MACHO", "B", 1)], expire=True)

    def moves(self, schedules):
        if self.end < START + timedelta(days=2):
            return
        day = self.end
        for worker, groups in schedules:
            source, destination = groups["ACABADO"][:2]
            self.send(worker, "CUY_MOVE", day, source_id=str(source.pen_id), destination_id=str(destination.pen_id),
                      items=[bucket("MACHO", "B", 2, occ=source)])
        kworker, kot = schedules[0]
        cworker, can = schedules[-1]
        for worker, receiver, source, destination in (
            (kworker, cworker, kot["ACABADO"][0], can["ACABADO"][2]),
            (cworker, kworker, can["ACABADO"][0], kot["ACABADO"][2]),
        ):
            dispatch_id = uuid4()
            self.send(worker, "CUY_DISPATCH", day, entity=dispatch_id, hour=10,
                      source_id=str(source.pen_id), destination_id=str(destination.pen_id),
                      items=[bucket("HEMBRA", "B", 1, occ=source)])
            self.send(receiver, "CUY_RECEIVE", day, hour=13, transfer_id=str(dispatch_id))


class Command(BaseCommand):
    help = "Reconstruye una CLONACIÓN local de demostración. Usar scripts/create_direction_demo.py."

    @transaction.atomic
    def handle(self, *args, **options):
        cfg = connection.settings_dict
        db = cfg["NAME"]
        if not (cfg["HOST"] in ("localhost", "127.0.0.1")
                and re.fullmatch(r"sitrap_demo_\d{8}_\d{6}", db)
                and os.environ.get("SITRAP_DEMO_REBUILD") == db
                and settings.CUY_SALES_PRIVATE_ROOT.parent.name == db):
            raise CommandError("Operación bloqueada fuera del clon local aislado.")
        demo = Demo(timezone.localdate() - timedelta(days=1))
        kotosh = Location.objects.get(kind="CENTRO", code="0001", active=True)
        canchan = Location.objects.get(kind="CENTRO", code="0002", active=True)
        point = Location.objects.get(kind="PUNTO_VENTA", code="0001V", active=True)
        admin = demo.assignment("ADMIN")
        producer, receiver = demo.assignment("PRODUCCION", kotosh), demo.assignment("RECEPCION", point)
        drivers = {c.id: demo.assignment("TRANSPORTE", c) for c in (kotosh, canchan)}
        workers = {c.id: demo.assignment("GALPONERO", c) for c in (kotosh, canchan)}
        selected = [admin, producer, receiver, *drivers.values(), *workers.values()]
        tables = [t for t in connection.introspection.table_names()
                  if t not in PRESERVE and (t in RESET_EXACT or t.startswith(RESET_PREFIXES))]
        # No CASCADE: a new dependency must be explicitly reviewed before purging the clone.
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE " + ", ".join(connection.ops.quote_name(t) for t in tables))
        # Historical simulation only. Shift the selected active access temporarily,
        # then restore the original timestamps before the transaction commits.
        RoleAssignment.objects.filter(pk__in=[a.id for a in selected]).update(starts_at=stamp(START, 0))
        demo.milk(kotosh, point, producer.user, drivers[kotosh.id].user, receiver.user)
        unit, _ = Unit.objects.get_or_create(code="UN", defaults={"name": "Unidad"})
        product, _ = Product.objects.get_or_create(code="CUYES", defaults=dict(unit=unit, name="Cuyes"))
        schedules = []
        expected = []
        for center, prefix, quantity, count, shed_count in ((kotosh, "KOT", 750, 24, 2),
                                                            (canchan, "CAN", 1500, 48, 1)):
            CenterProduct.objects.update_or_create(center=center, product=product, defaults={"enabled": True})
            assignment = workers[center.id]
            for index in range(1, shed_count + 1):
                shed = Shed.objects.create(center=center, code=f"{prefix}-G{index:02}",
                                           name=f"Galpón {index} de {center.name}")
                ShedGrant.objects.create(shed=shed, assignment=assignment)
                groups = demo.make_pens(shed, assignment.user, quantity, count)
                demo.cuyes(center, groups, shed, admin.user, assignment.user, drivers[center.id].user, point)
                schedules.append((assignment.user, groups))
                expected.append((shed, count, quantity))
        demo.moves(schedules)
        for shed, count, quantity in expected:
            actual = Balance.objects.filter(occupation__pen__shed=shed).aggregate(n=Sum("quantity"))["n"]
            if actual != quantity:
                raise CommandError(f"{shed.code}: esperado {quantity}, registrado {actual}.")
            self.stdout.write(f"{shed.code}: {count} pozas, {actual} cuyes al corte")
        for a in selected:
            RoleAssignment.objects.filter(pk=a.id).update(starts_at=a.starts_at)
        if not active_assignments(admin.user).filter(role_id="ADMIN").exists():
            raise CommandError("La cuenta administrativa no se conservó.")
        self.stdout.write(f"Historial ficticio: {START} a {demo.end}.")
