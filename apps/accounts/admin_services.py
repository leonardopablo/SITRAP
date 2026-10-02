from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.accounts.access import require_admin
from apps.accounts.models import RoleAssignment, User
from apps.audit.services import record
from apps.common.errors import DomainError
from apps.common.services import lock_rows
from apps.sync.services import ensure_actor


def lock_admin_and_target(actor, target_id):
    users = {user.pk: user for user in lock_rows(User, {actor.pk, target_id})}
    actor = users[actor.pk]
    ensure_actor(actor)
    require_admin(actor)
    return actor, users.get(target_id)


def user_snapshot(user):
    return {
        key: getattr(user, key)
        for key in ("id", "username", "name", "is_active", "password_change_required")
    }


@transaction.atomic
def create_user(actor, data):
    actor, existing = lock_admin_and_target(actor, data["id"])
    if existing:
        if (
            existing.username == data["username"]
            and existing.name == data["name"]
            and existing.password_change_required
            and existing.check_password(data["temporary_password"])
        ):
            return existing
        raise DomainError("IDEMPOTENCY_CONFLICT", "El UUID de cuenta ya existe con otros datos.")
    user = User(
        id=data["id"], username=data["username"], name=data["name"], password_change_required=True
    )
    validate_password(data["temporary_password"], user)
    user.set_password(data["temporary_password"])
    user.full_clean()
    try:
        with transaction.atomic():
            user.save(force_insert=True)
    except IntegrityError:
        raise DomainError("VALIDATION_ERROR", "El usuario o UUID ya existe.", 422)
    record(actor, "user", user.id, "CREATE_USER", after=user_snapshot(user))
    return user


@transaction.atomic
def update_user(actor, target_id, data):
    actor, target = lock_admin_and_target(actor, target_id)
    if target is None:
        raise DomainError("NOT_FOUND", "Cuenta no disponible.", 404)
    before = user_snapshot(target)
    for key, value in data.items():
        setattr(target, key, value)
    target.full_clean()
    after = user_snapshot(target)
    if before != after:
        try:
            with transaction.atomic():
                target.save(update_fields=list(data))
        except IntegrityError:
            raise DomainError("VALIDATION_ERROR", "El usuario ya existe.", 422)
        record(actor, "user", target.id, "UPDATE_USER", before=before, after=after)
    return target


@transaction.atomic
def reset_password(actor, target_id, temporary_password):
    actor, target = lock_admin_and_target(actor, target_id)
    if target is None:
        raise DomainError("NOT_FOUND", "Cuenta no disponible.", 404)
    validate_password(temporary_password, target)
    if target.password_change_required and target.check_password(temporary_password):
        return target
    target.set_password(temporary_password)
    target.password_change_required = True
    target.save(update_fields=["password", "password_change_required"])
    record(actor, "user", target.id, "RESET_PASSWORD", after={"password_change_required": True})
    return target


def assignment_snapshot(assignment):
    return {
        key: getattr(assignment, key)
        for key in ("id", "user_id", "role_id", "scope", "location_id", "starts_at", "ends_at")
    }


@transaction.atomic
def save_assignment(actor, data, assignment_id=None):
    assignment = RoleAssignment.objects.filter(pk=assignment_id).first() if assignment_id else None
    if assignment_id and assignment is None:
        raise DomainError("NOT_FOUND", "Asignación no disponible.", 404)
    target_id = assignment.user_id if assignment else data["user_id"]
    actor, target = lock_admin_and_target(actor, target_id)
    if target is None or not target.is_active:
        raise DomainError("VALIDATION_ERROR", "Cuenta destino no activa.", 422)
    if assignment:
        assignment = RoleAssignment.objects.select_for_update().get(pk=assignment.pk)
    else:
        existing = RoleAssignment.objects.filter(pk=data["id"]).first()
        if existing:
            if all(getattr(existing, key) == value for key, value in data.items()):
                return existing
            raise DomainError("IDEMPOTENCY_CONFLICT", "UUID de asignación ya utilizado.")
    before = assignment_snapshot(assignment) if assignment else {}
    assignment = assignment or RoleAssignment()
    for key, value in data.items():
        setattr(assignment, key, value)
    assignment.full_clean()
    if assignment.location_id and not assignment.location.active:
        raise DomainError("VALIDATION_ERROR", "Ubicación inactiva.", 422)
    overlapping = (
        RoleAssignment.objects.filter(
            user_id=assignment.user_id,
            role_id=assignment.role_id,
            scope=assignment.scope,
            location_id=assignment.location_id,
        )
        .exclude(pk=assignment.pk)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=assignment.starts_at))
    )
    if assignment.ends_at:
        overlapping = overlapping.filter(starts_at__lt=assignment.ends_at)
    if overlapping.exists():
        raise DomainError(
            "VALIDATION_ERROR", "La asignación se superpone con otra del mismo ámbito.", 422
        )
    after = assignment_snapshot(assignment)
    if before != after:
        try:
            with transaction.atomic():
                assignment.save()
        except IntegrityError:
            raise DomainError("VALIDATION_ERROR", "Asignación duplicada o inválida.", 422)
        record(
            actor, "role_assignment", assignment.id, "SAVE_ASSIGNMENT", before=before, after=after
        )
    return assignment
