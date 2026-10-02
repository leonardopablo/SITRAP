import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from apps.accounts.models import User
from apps.audit.models import AuditEntry
from apps.notifications.models import PushSubscription
from apps.sync.models import Device
from tests.test_access import assign
from tests.test_transfer_reads import client_for

pytestmark = pytest.mark.django_db


def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


@pytest.fixture
def vapid(settings):
    key = ec.generate_private_key(ec.SECP256R1())
    settings.PUSH_ENABLED = True
    settings.VAPID_PRIVATE_KEY = b64(
        key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    settings.VAPID_PUBLIC_KEY = b64(
        key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
    )
    settings.VAPID_SUBJECT = "mailto:ops@example.org"
    return settings.VAPID_PUBLIC_KEY


def subscription_data(device, suffix="token"):
    key = ec.generate_private_key(ec.SECP256R1())
    return {
        "device_id": str(device.id),
        "endpoint": f"https://fcm.googleapis.com/fcm/send/{suffix}",
        "keys": {
            "p256dh": b64(
                key.public_key().public_bytes(
                    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
                )
            ),
            "auth": b64(b"0123456789abcdef"),
        },
    }


def test_subscription_ownership_replay_config_and_secret_redaction(user, vapid):
    device = Device.objects.create(user=user, name="phone")
    client = client_for(user)
    assert client.get("/api/v1/push/config").json() == {"enabled": True, "vapid_public_key": vapid}
    data = subscription_data(device)
    first = client.post("/api/v1/push/subscriptions", data, format="json")
    assert first.status_code == 200, first.data
    assert client.post("/api/v1/push/subscriptions", data, format="json").json() == first.json()
    assert PushSubscription.objects.count() == 1
    assert "endpoint" not in first.json() and "keys" not in first.json()
    assert data["keys"]["auth"] not in str(list(AuditEntry.objects.values("before", "after")))
    other = User.objects.create_user(username="other")
    assert (
        client_for(other).post("/api/v1/push/subscriptions", data, format="json").status_code == 403
    )
    assert (
        client.delete(
            f"/api/v1/push/subscriptions/{first.json()['id']}", HTTP_X_DEVICE_ID=str(device.id)
        ).status_code
        == 204
    )
    assert (
        client.delete(
            f"/api/v1/push/subscriptions/{first.json()['id']}", HTTP_X_DEVICE_ID=str(device.id)
        ).status_code
        == 204
    )


def test_logout_revokes_device_and_account_deactivation_revokes_all(user, vapid):
    first, second = (
        Device.objects.create(user=user, name="phone"),
        Device.objects.create(user=user, name="tablet"),
    )
    client = client_for(user)
    client.post("/api/v1/push/subscriptions", subscription_data(first, "first"), format="json")
    client.post("/api/v1/push/subscriptions", subscription_data(second, "second"), format="json")
    assert client.post("/api/v1/auth/logout", HTTP_X_DEVICE_ID=str(first.id)).status_code == 204
    assert not PushSubscription.objects.get(device=first).active
    assert PushSubscription.objects.get(device=second).active
    admin = User.objects.create_user(username="admin")
    assign(admin, "ADMIN")
    assert (
        client_for(admin)
        .patch(f"/api/v1/users/{user.id}", {"is_active": False}, format="json")
        .status_code
        == 200
    )
    assert not PushSubscription.objects.filter(active=True).exists()


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/x",
        "https://127.0.0.1/x",
        "https://fcm.googleapis.com.evil.test/x",
        "https://user@fcm.googleapis.com/x",
    ],
)
def test_untrusted_endpoint_rejected(user, vapid, endpoint):
    device = Device.objects.create(user=user, name="phone")
    data = {**subscription_data(device), "endpoint": endpoint}
    assert (
        client_for(user).post("/api/v1/push/subscriptions", data, format="json").status_code == 422
    )
    assert not PushSubscription.objects.exists()


def test_disabled_config_invalid_keys_and_vapid_file_no_overwrite(user, settings, tmp_path):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    client = client_for(user)
    assert client.get("/api/v1/push/config").json() == {"enabled": False, "vapid_public_key": None}
    device = Device.objects.create(user=user, name="phone")
    data = subscription_data(device)
    data["keys"]["auth"] = "invalid"
    assert client.post("/api/v1/push/subscriptions", data, format="json").status_code == 422
    output = tmp_path / "vapid.env"
    call_command("generate_vapid", output=str(output), subject="mailto:ops@example.org")
    original = output.read_bytes()
    with pytest.raises(CommandError):
        call_command("generate_vapid", output=str(output), subject="mailto:ops@example.org")
    assert output.read_bytes() == original


def test_invalid_vapid_configuration_fails_closed_without_exposing_secret(user, settings):
    from apps.notifications.checks import check_vapid

    settings.PUSH_ENABLED = True
    settings.VAPID_PRIVATE_KEY = "do-not-expose-this-private-key"
    settings.VAPID_PUBLIC_KEY = "invalid"
    response = client_for(user).get("/api/v1/push/config")
    assert response.json() == {"enabled": False, "vapid_public_key": None}
    errors = check_vapid(None)
    assert errors[0].id == "notifications.E001"
    assert settings.VAPID_PRIVATE_KEY not in str(errors)


def test_pinned_library_vapid_and_encryption_roundtrip(vapid, settings):
    import http_ece
    from py_vapid import Vapid02
    from pywebpush import WebPusher

    key = ec.generate_private_key(ec.SECP256R1())
    auth = b"0123456789abcdef"
    info = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/test",
        "keys": {
            "p256dh": b64(
                key.public_key().public_bytes(
                    serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
                )
            ),
            "auth": b64(auth),
        },
    }
    assert Vapid02.from_string(settings.VAPID_PRIVATE_KEY).public_key
    payload = b'{"title":"SITRAP","body":"Consulte la aplicacion"}'
    ciphertext = WebPusher(info).encode(payload)["body"]
    assert ciphertext != payload
    assert (
        http_ece.decrypt(ciphertext, private_key=key, auth_secret=auth, version="aes128gcm")
        == payload
    )
