import base64
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from rest_framework import serializers


def decode_key(value):
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except (ValueError, TypeError):
        raise serializers.ValidationError("Clave base64url no válida.") from None


def validate_endpoint(value):
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        permitted = any(
            host == allowed or (allowed.startswith(".") and host.endswith(allowed))
            for allowed in settings.PUSH_ALLOWED_HOSTS
        )
        valid = (
            value.isascii()
            and not any(ord(char) <= 32 for char in value)
            and parsed.scheme == "https"
            and parsed.port in [None, 443]
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
            and parsed.path
            and permitted
        )
    except ValueError:
        valid = False
    if not valid:
        raise serializers.ValidationError("Se requiere endpoint HTTPS de un proveedor permitido.")
    return value


def private_key():
    try:
        key = serialization.load_der_private_key(
            decode_key(settings.VAPID_PRIVATE_KEY), password=None
        )
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
            key.curve, ec.SECP256R1
        ):
            raise ValueError()
        public = key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        if public != decode_key(settings.VAPID_PUBLIC_KEY):
            raise ValueError()
        subject = settings.VAPID_SUBJECT
        if not (
            subject.startswith("mailto:") and "@" in subject[7:] or subject.startswith("https://")
        ):
            raise ValueError()
        return key
    except Exception:
        raise ValueError("Configuración VAPID inválida o claves no coincidentes.") from None


def public_config():
    if not settings.PUSH_ENABLED:
        return {"enabled": False, "vapid_public_key": None}
    try:
        private_key()
    except ValueError:
        return {"enabled": False, "vapid_public_key": None}
    return {"enabled": True, "vapid_public_key": settings.VAPID_PUBLIC_KEY}
