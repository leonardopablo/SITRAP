import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction

from apps.audit.models import AuditEntry
from apps.audit.services import atomic_change, record
from apps.catalog.models import Location
from apps.common.errors import DomainError
from apps.common.services import check_version
from apps.sync.models import Device, SyncOperation
from apps.sync.services import execute
from tests.test_sync_base import allow, create_location, event

pytestmark = pytest.mark.django_db


def test_success_is_audited_once_and_replay_does_not_duplicate(user):
    device = Device.objects.create(user=user, name="test")
    command = event(device)
    execute(user, command, create_location, allow)
    execute(user, command, create_location, allow)
    entry = AuditEntry.objects.get()
    assert entry.actor == user and entry.operation_id == uuid.UUID(command["event_id"])


def test_audit_failure_rolls_back_operation_and_business_change(user):
    device = Device.objects.create(user=user, name="test")
    command = event(device)
    with patch("apps.audit.services.record", side_effect=RuntimeError("audit storage unavailable")):
        with pytest.raises(RuntimeError):
            execute(user, command, create_location, allow)
    assert not Location.objects.exists()
    assert not SyncOperation.objects.exists()
    assert not AuditEntry.objects.exists()


def test_append_only_database_and_secret_redaction(user):
    with transaction.atomic():
        entry = record(
            user,
            "test",
            uuid.uuid4(),
            "CHANGE",
            after={
                "password": "secret",
                "nested": {"endpoint": "https://secret"},
                "liters": Decimal("2.000"),
            },
        )
    assert entry.after == {
        "password": "[REDACTED]",
        "nested": {"endpoint": "[REDACTED]"},
        "liters": "2.000",
    }
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditEntry.objects.filter(pk=entry.pk).update(action="REWRITE")
    with pytest.raises(IntegrityError), transaction.atomic():
        entry.delete()
    assert AuditEntry.objects.get().action == "CHANGE"


def test_atomic_change_and_version_guards(user):
    entity_id = uuid.uuid4()

    def change():
        Location.objects.create(id=entity_id, code="C1", name="A", kind="CENTRO")
        return {"name": "A"}

    with patch("apps.audit.services.record", side_effect=RuntimeError("fail")):
        with pytest.raises(RuntimeError):
            atomic_change(user, "location", entity_id, "CREATE", change)
    assert not Location.objects.exists()
    with pytest.raises(DomainError) as error:
        check_version(SimpleNamespace(lock_version=2), 1)
    assert error.value.detail["code"] == "VERSION_CONFLICT"
    check_version(SimpleNamespace(lock_version=2), 2)


@pytest.mark.django_db(transaction=True)
def test_audit_requires_business_transaction():
    with pytest.raises(RuntimeError):
        record(None, "test", uuid.uuid4(), "CHANGE")
