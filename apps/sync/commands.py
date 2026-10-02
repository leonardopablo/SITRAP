from apps.common.errors import DomainError
from apps.sync.services import execute


def registry():
    # Imported lazily so models/apps load before domain commands.
    from apps.milk.serializers import (
        MilkingConfirmCommand,
        MilkingCreateCommand,
        MilkingUpdateCommand,
    )
    from apps.milk.services import (
        authorize_milking,
        confirm_milking,
        create_milking,
        update_milking,
    )

    return {
        "MILKING_CONFIRM": (MilkingConfirmCommand, confirm_milking, authorize_milking),
        "MILKING_CREATE": (MilkingCreateCommand, create_milking, authorize_milking),
        "MILKING_UPDATE": (MilkingUpdateCommand, update_milking, authorize_milking),
    }


def dispatch(actor, command, *, fixed_type=None, entity_id=None):
    command = dict(command)
    if fixed_type:
        if command.get("type", fixed_type) != fixed_type:
            raise DomainError("VALIDATION_ERROR", "Tipo incompatible con la ruta.", 422)
        command["type"] = fixed_type
    if entity_id and str(command.get("entity_id")) != str(entity_id):
        raise DomainError("VALIDATION_ERROR", "entity_id no coincide con la ruta.", 422)
    entry = registry().get(command.get("type"))
    if entry is None:
        raise DomainError("VALIDATION_ERROR", "Comando no implementado.", 422)
    serializer_class, handler, authorize = entry
    serializer = serializer_class(data=command)
    serializer.is_valid(raise_exception=True)
    return execute(actor, serializer.validated_data, handler, authorize)
