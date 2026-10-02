"""Explicit, audited break-glass recovery when no active business ADMIN remains."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import RoleAssignment, User
from apps.audit.services import record


class Command(BaseCommand):
    help = "Restore ADMIN access by creating a new assignment; never reopen historical assignments."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--confirm-no-admin", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm_no_admin"]:
            raise CommandError("Confirm recovery explicitly with --confirm-no-admin.")
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(81403008)")
        now = timezone.now()
        if RoleAssignment.objects.filter(
            role_id="ADMIN", scope="GLOBAL", user__is_active=True, starts_at__lte=now
        ).filter(ends_at__isnull=True).exists() or RoleAssignment.objects.filter(
            role_id="ADMIN", scope="GLOBAL", user__is_active=True, starts_at__lte=now,
            ends_at__gt=now
        ).exists():
            raise CommandError("An active ADMIN exists; use the authenticated accounts API.")
        user = User.objects.filter(username=options["username"], is_active=True).first()
        if user is None:
            raise CommandError("Active user not found; no assignment created.")
        if RoleAssignment.objects.filter(user=user, role_id="ADMIN", scope="GLOBAL").filter(
            ends_at__isnull=True
        ).exists():
            raise CommandError("An open ADMIN assignment already exists for this user.")
        assignment = RoleAssignment.objects.create(user=user, role_id="ADMIN", scope="GLOBAL")
        record(
            user, "role_assignment", assignment.id, "RECOVER_ADMIN",
            after={"user_id": str(user.id), "role": "ADMIN", "scope": "GLOBAL"},
            reason="Explicit operator recovery: no active ADMIN remained.",
        )
        self.stdout.write(self.style.SUCCESS("ADMIN access restored; sign out and sign in again."))
