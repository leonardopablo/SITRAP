from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.sync.models import SyncSnapshot


class Command(BaseCommand):
    help = "Count or delete only expired sync snapshots; never touches operations."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args, **options):
        limit = options["batch_size"]
        if not 1 <= limit <= 10000:
            raise CommandError("--batch-size must be between 1 and 10000.")
        cutoff = timezone.now()
        expired = SyncSnapshot.objects.filter(expires_at__lt=cutoff)
        if not options["apply"]:
            self.stdout.write(f"Expired snapshots: {expired.count()} (dry run)")
            return
        removed = 0
        while True:
            with transaction.atomic():
                ids = list(expired.order_by("expires_at", "id").values_list("id", flat=True)[:limit])
                if not ids:
                    break
                count, _ = SyncSnapshot.objects.filter(id__in=ids, expires_at__lt=cutoff).delete()
                removed += count
        self.stdout.write(f"Expired snapshots removed: {removed}")
