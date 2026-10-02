from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.sync.models import Device, SyncSnapshot


@pytest.mark.django_db
def test_snapshot_prune_dry_run_batches_and_preserves_live_data(user):
    device = Device.objects.create(user=user, name="demo")
    past, future = timezone.now() - timedelta(days=1), timezone.now() + timedelta(days=1)
    for expiry in (past, past, future):
        SyncSnapshot.objects.create(device=device, scope_hash="x", entries=[], changes=[], expires_at=expiry)
    output = StringIO()
    call_command("prune_sync_snapshots", stdout=output)
    assert "2 (dry run)" in output.getvalue()
    assert SyncSnapshot.objects.count() == 3
    with pytest.raises(CommandError):
        call_command("prune_sync_snapshots", apply=True, batch_size=0)
    call_command("prune_sync_snapshots", apply=True, batch_size=1)
    assert list(SyncSnapshot.objects.values_list("expires_at", flat=True)) == [future]
    assert Device.objects.filter(pk=device.pk).exists()
