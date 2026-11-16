from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.access import require_admin
from apps.accounts.models import User
from apps.common.errors import DomainError
from apps.cuyes.models import SaleReservation
from apps.cuyes.sales_services import expire_one


class Command(BaseCommand):
    help = "Libera reservas comerciales impagas vencidas, en lotes idempotentes."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Cuenta ADMIN responsable del proceso auditado.")
        parser.add_argument("--batch-size", type=int, default=200)

    def handle(self, *args, **options):
        actor = User.objects.filter(username=options["username"], is_active=True).first()
        if not actor:
            raise CommandError("Cuenta responsable no disponible.")
        try:
            require_admin(actor)
        except DomainError as exc:
            raise CommandError(str(exc.detail["message"]))
        limit = options["batch_size"]
        if limit < 1 or limit > 1000:
            raise CommandError("batch-size debe estar entre 1 y 1000.")
        ids = list(SaleReservation.objects.filter(
            state="IMPAGA", expires_at__lte=timezone.now(),
        ).order_by("expires_at", "id").values_list("id", flat=True)[:limit])
        expired = sum(expire_one(actor, pk) for pk in ids)
        self.stdout.write(f"Reservas vencidas liberadas: {expired}")
