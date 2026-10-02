import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.models import RoleAssignment, User
from apps.audit.services import record


class Command(BaseCommand):
    help = "Create the first business ADMIN; refuses when a global ADMIN already exists."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--name", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(81403008)")
        if RoleAssignment.objects.filter(role_id="ADMIN", scope="GLOBAL").exists():
            raise CommandError("An ADMIN already exists; use the authenticated accounts API.")
        if User.objects.filter(username=options["username"]).exists():
            raise CommandError("Username already exists.")
        password = os.environ.get("SITRAP_BOOTSTRAP_PASSWORD")
        if password is None:
            password = getpass.getpass("Initial password: ")
            if password != getpass.getpass("Repeat password: "):
                raise CommandError("Passwords differ.")
        user = User(
            username=options["username"], name=options["name"], password_change_required=True
        )
        validate_password(password, user)
        user.set_password(password)
        user.full_clean()
        user.save()
        RoleAssignment.objects.create(user=user, role_id="ADMIN", scope="GLOBAL")
        record(user, "user", user.id, "BOOTSTRAP_ADMIN", after={"username": user.username})
        self.stdout.write(self.style.SUCCESS("ADMIN created; password change is required."))
