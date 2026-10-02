import json

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Max, Min
from django.utils import timezone

from apps.notifications.models import PushDelivery, WorkerHeartbeat


class Command(BaseCommand):
    help = "Estado de cola y latido, sin datos privados ni endpoints."

    def add_arguments(self, parser):
        parser.add_argument("--max-age", type=int, default=120)

    def handle(self, *args, **options):
        last = WorkerHeartbeat.objects.aggregate(last=Max("seen_at"))["last"]
        counts = dict(
            PushDelivery.objects.values("state")
            .annotate(total=Count("id"))
            .values_list("state", "total")
        )
        oldest = PushDelivery.objects.filter(state__in=["PENDIENTE", "REINTENTABLE"]).aggregate(
            at=Min("next_attempt_at")
        )["at"]
        self.stdout.write(
            json.dumps(
                {
                    "counts": counts,
                    "last_heartbeat": last.isoformat() if last else None,
                    "oldest_due_seconds": max(0, int((timezone.now() - oldest).total_seconds()))
                    if oldest
                    else 0,
                }
            )
        )
        if last is None or (timezone.now() - last).total_seconds() > options["max_age"]:
            raise CommandError("No hay latido reciente del worker.")
