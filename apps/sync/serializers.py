from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime
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
    preparation_valid = serializers.SerializerMethodField()

    def get_preparation_valid(self, obj) -> bool:
        return bool(
            obj.active
            and obj.prepared_at
            and obj.preparation_expires_at
            and obj.preparation_expires_at > timezone.now()
        )

    class Meta:
        model = Device
        fields = (
            "id",
            "name",
            "active",
            "prepared_at",
            "preparation_expires_at",
            "preparation_valid",
            "last_contact_at",
        )
        read_only_fields = fields


class ZonedDateTimeField(serializers.DateTimeField):
    def to_internal_value(self, value):
        try:
            parsed = value if isinstance(value, datetime) else parse_datetime(value)
        except (ValueError, TypeError):
            parsed = None
        if parsed is not None and timezone.is_naive(parsed):
            raise serializers.ValidationError("Incluya zona horaria u offset.")
        return super().to_internal_value(value)


class EnvelopeSerializer(StrictSerializer):
    event_id = serializers.UUIDField()
    device_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=COMMAND_TYPES)
    entity_id = serializers.UUIDField()
    occurred_at = ZonedDateTimeField()
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
