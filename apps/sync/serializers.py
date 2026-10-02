from rest_framework import serializers

from apps.common.serializers import StrictSerializer
from apps.sync.models import Device, SyncOperation

# Executable command catalogue. Payload validators arrive with each domain task.
COMMAND_TYPES = (
    "MILKING_CREATE",
    "MILKING_UPDATE",
    "MILKING_CONFIRM",
    "MILKING_RECTIFY",
    "MILKING_VOID",
    "TRANSFER_CREATE",
    "TRANSFER_UPDATE",
    "TRANSFER_SEND",
    "TRANSFER_REVISE",
    "TRANSFER_CANCEL",
    "TRANSFER_PICKUP",
    "TRANSFER_RECEIVE",
    "CORRECTION_CREATE",
    "CORRECTION_ACCEPT",
    "CORRECTION_REJECT",
    "CORRECTION_WITHDRAW",
)


class DeviceInputSerializer(StrictSerializer):
    id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = (
            "id",
            "name",
            "active",
            "prepared_at",
            "preparation_expires_at",
            "last_contact_at",
        )
        read_only_fields = fields


class EnvelopeSerializer(StrictSerializer):
    event_id = serializers.UUIDField()
    device_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=COMMAND_TYPES)
    entity_id = serializers.UUIDField()
    occurred_at = serializers.DateTimeField()
    expected_version = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    depends_on = serializers.ListField(child=serializers.UUIDField(), max_length=100, default=list)
    payload = serializers.DictField()

    def validate(self, data):
        deps = data["depends_on"]
        if data["event_id"] in deps or len(deps) != len(set(deps)):
            raise serializers.ValidationError(
                {"depends_on": "Dependencias duplicadas o autorreferencia."}
            )
        return data


class OperationResultSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=SyncOperation.State.choices)
    entity_id = serializers.UUIDField()
    lock_version = serializers.IntegerField(allow_null=True)
    result = serializers.DictField()
    error = serializers.DictField(allow_null=True)
    server_received_at = serializers.DateTimeField()
