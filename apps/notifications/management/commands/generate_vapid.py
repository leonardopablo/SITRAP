import base64
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Genera claves VAPID en un archivo nuevo; nunca imprime la clave privada."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--subject", required=True)

    def handle(self, *args, **options):
        path = Path(options["output"]).resolve()
        if not options["subject"].startswith(("mailto:", "https://")):
            raise CommandError("Indique contacto mailto: o HTTPS.")
        key = ec.generate_private_key(ec.SECP256R1())

        def encode(value):
            return base64.urlsafe_b64encode(value).decode().rstrip("=")

        private = encode(
            key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        public = encode(
            key.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        )
        data = f"PUSH_ENABLED=True\nVAPID_PRIVATE_KEY={private}\nVAPID_PUBLIC_KEY={public}\nVAPID_SUBJECT={options['subject']}\n"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(data)
        except OSError:
            raise CommandError(
                "No se pudo crear el archivo nuevo; no se sobrescriben claves."
            ) from None
        self.stdout.write(f"Claves guardadas en {path}. Proteja el archivo y no lo incluya en Git.")
