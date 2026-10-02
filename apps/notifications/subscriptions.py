from cryptography.hazmat.primitives.asymmetric import ec
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.audit.services import record
from apps.common.errors import DomainError
from apps.common.serializers import StrictSerializer
from apps.sync.services import ensure_actor, owned_device

from .models import PushSubscription
from .push_config import decode_key, public_config, validate_endpoint


class PushKeys(StrictSerializer):
    p256dh = serializers.CharField(max_length=128)
    auth = serializers.CharField(max_length=64)

    def validate(self, data):
        if len(decode_key(data["auth"])) != 16:
            raise serializers.ValidationError({"auth": "Se requieren 16 bytes."})
        try:
            public = decode_key(data["p256dh"])
            if len(public) != 65 or public[0] != 4:
                raise ValueError()
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
        except ValueError:
            raise serializers.ValidationError(
                {"p256dh": "Clave pública P-256 no válida."}
            ) from None
        return data


class SubscriptionInput(StrictSerializer):
    device_id = serializers.UUIDField()
    endpoint = serializers.CharField(
        max_length=2048, validators=[validate_endpoint], trim_whitespace=False
    )
    keys = PushKeys()


class SubscriptionSerializer(serializers.ModelSerializer):
    device_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PushSubscription
        fields = ["id", "device_id", "active", "created_at", "updated_at", "revoked_at"]


@transaction.atomic
def subscribe(actor, data):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    ensure_actor(actor)
    device = owned_device(actor, data["device_id"], lock=True)
    if not public_config()["enabled"]:
        raise DomainError("PUSH_UNAVAILABLE", "Los avisos al teléfono no están habilitados.", 409)
    existing = (
        PushSubscription.objects.select_for_update().filter(endpoint=data["endpoint"]).first()
    )
    if existing and (existing.user_id != actor.id or existing.device_id != device.id):
        raise DomainError(
            "PERMISSION_DENIED", "La suscripción pertenece a otra cuenta o dispositivo.", 403
        )
    changed = (
        not existing
        or not existing.active
        or existing.p256dh != data["keys"]["p256dh"]
        or existing.auth != data["keys"]["auth"]
    )
    subscription = existing or PushSubscription(
        user=actor, device=device, endpoint=data["endpoint"]
    )
    subscription.p256dh, subscription.auth = data["keys"]["p256dh"], data["keys"]["auth"]
    subscription.active, subscription.revoked_at = True, None
    if changed:
        try:
            with transaction.atomic():
                subscription.save()
        except IntegrityError:
            raise DomainError("IDEMPOTENCY_CONFLICT", "El endpoint ya está registrado.")
        record(
            actor,
            "push_subscription",
            subscription.id,
            "SUBSCRIBE_PUSH",
            after={"device_id": device.id, "active": True},
        )
    return subscription


@transaction.atomic
def unsubscribe(actor, device_id, subscription_id):
    actor = User.objects.select_for_update(no_key=True).get(pk=actor.pk)
    ensure_actor(actor)
    device = owned_device(actor, device_id)
    subscription = (
        PushSubscription.objects.select_for_update()
        .filter(pk=subscription_id, user=actor, device=device)
        .first()
    )
    if subscription is None:
        raise DomainError("NOT_FOUND", "Suscripción no disponible.", 404)
    if subscription.active:
        subscription.active, subscription.revoked_at = False, timezone.now()
        subscription.save(update_fields=["active", "revoked_at", "updated_at"])
        record(
            actor, "push_subscription", subscription.id, "UNSUBSCRIBE_PUSH", after={"active": False}
        )


def revoke_subscriptions(user_id, device_id=None):
    query = PushSubscription.objects.filter(user_id=user_id, active=True)
    if device_id:
        query = query.filter(device_id=device_id)
    return query.update(active=False, revoked_at=timezone.now(), updated_at=timezone.now())
