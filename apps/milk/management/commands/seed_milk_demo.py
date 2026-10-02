import uuid
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, RoleAssignment, User
from apps.catalog.models import (
    Animal,
    AnimalStay,
    CenterProduct,
    Location,
    Product,
    Species,
    Turn,
    Unit,
)
from apps.sync.commands import dispatch
from apps.sync.models import Device


class Command(BaseCommand):
    help = "Create a confirmed milk demo in a development database only."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-demo", action="store_true")
        parser.add_argument("--date", type=date.fromisoformat, default=date.today)

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not options["confirm_demo"]:
            raise CommandError("Demo requires DEBUG and --confirm-demo; never run in production.")
        if Location.objects.filter(code="DEMO_LECHE").exists():
            raise CommandError("Demo already exists; no existing records were changed.")
        for model, code in (
            (Product, "DEMO_LECHE"),
            (Species, "DEMO_BOVINO"),
            (Turn, "DEMO_MANANA"),
            (Animal, "DEMO_VACA_1"),
            (Animal, "DEMO_VACA_2"),
        ):
            if model.objects.filter(code=code).exists():
                raise CommandError(f"Code {code} already exists; no existing records were changed.")
        if User.objects.filter(username="demo_leche").exists():
            raise CommandError("Username demo_leche already exists.")

        Unit.objects.get_or_create(code="L", defaults={"name": "Litro"})
        Role.objects.get_or_create(code="PRODUCCION")
        center = Location.objects.create(code="DEMO_LECHE", name="Centro demo leche", kind="CENTRO")
        product = Product.objects.create(code="DEMO_LECHE", name="Leche demo", unit_id="L")
        CenterProduct.objects.create(center=center, product=product)
        turn = Turn.objects.create(code="DEMO_MANANA", name="Mañana demo")
        species = Species.objects.create(code="DEMO_BOVINO", name="Bovino demo")
        cows = [
            Animal.objects.create(code=f"DEMO_VACA_{n}", species=species, sex="HEMBRA")
            for n in (1, 2)
        ]
        for cow in cows:
            AnimalStay.objects.create(animal=cow, center=center, starts_on=options["date"])
        actor = User(username="demo_leche", name="Operador demo")
        actor.set_unusable_password()
        actor.save()
        RoleAssignment.objects.create(
            user=actor, role_id="PRODUCCION", scope="UBICACION", location=center
        )
        device = Device.objects.create(user=actor, name="Semilla demo")
        milking_id, production_id, version_id = (str(uuid.uuid4()) for _ in range(3))
        command = {
            "event_id": str(uuid.uuid4()),
            "device_id": str(device.id),
            "type": "MILKING_CREATE",
            "entity_id": milking_id,
            "occurred_at": timezone.now().isoformat(),
            "depends_on": [],
            "payload": {
                "production_id": production_id,
                "version_id": version_id,
                "center_id": str(center.id),
                "product_id": str(product.id),
                "date": options["date"].isoformat(),
                "turn_id": str(turn.id),
                "details": [
                    {"animal_id": str(cows[0].id), "liters": "2.500"},
                    {"animal_id": str(cows[1].id), "liters": "3.000"},
                ],
            },
        }
        _, status = dispatch(actor, command, fixed_type="MILKING_CREATE")
        if status != 200:
            raise CommandError("Could not create demo milking; transaction rolled back.")
        confirm = {
            **command,
            "event_id": str(uuid.uuid4()),
            "type": "MILKING_CONFIRM",
            "expected_version": 1,
            "payload": {"version_id": version_id, "lot_id": str(uuid.uuid4())},
        }
        _, status = dispatch(actor, confirm, fixed_type="MILKING_CONFIRM")
        if status != 200:
            raise CommandError("Could not confirm demo milking; transaction rolled back.")
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo confirmed: center={center.id} product={product.id} "
                f"date={options['date']} milking={milking_id} liters=5.500"
            )
        )
