import os
import socket
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.notifications.worker import run_once


class Command(BaseCommand):
    help = "Procesa la outbox Web Push con leases recuperables."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--batch-size", type=int, default=20)
        parser.add_argument("--worker-id", default=f"{socket.gethostname()}-{os.getpid()}")

    def handle(self, *args, **options):
        if not 1 <= options["batch_size"] <= 100 or len(options["worker_id"]) > 100:
            raise CommandError("Tamaño 1-100 e identificador de hasta 100 caracteres.")
        try:
            while True:
                try:
                    count = run_once(worker_id=options["worker_id"], limit=options["batch_size"])
                except ValueError as exc:
                    raise CommandError(str(exc)) from None
                if options["once"]:
                    self.stdout.write(f"Intentos procesados: {count}")
                    return
                if count == 0:
                    time.sleep(settings.PUSH_POLL_SECONDS)
        except KeyboardInterrupt:
            self.stdout.write("Worker detenido; los leases pendientes se recuperan al vencer.")
