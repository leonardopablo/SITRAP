from decimal import Decimal

from rest_framework import serializers

from apps.common.serializers import StrictSerializer
from apps.sync.serializers import EnvelopeSerializer, OperationResultSerializer


class CowDetail(StrictSerializer):
    animal_id = serializers.UUIDField()
    liters = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0"), allow_null=True
    )


class MilkingCreatePayload(StrictSerializer):
    replaces_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    production_id = serializers.UUIDField()
    version_id = serializers.UUIDField()
    center_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    date = serializers.DateField()
    turn_id = serializers.UUIDField()
    details = CowDetail(many=True, max_length=500, allow_empty=True)


class MilkingUpdatePayload(StrictSerializer):
    date = serializers.DateField()
    turn_id = serializers.UUIDField()
    details = CowDetail(many=True, max_length=500, allow_empty=True)


class MilkingCreateCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["MILKING_CREATE"], default="MILKING_CREATE")
    payload = MilkingCreatePayload()

    def validate(self, data):
        data = super().validate(data)
        if data.get("expected_version") is not None:
            raise serializers.ValidationError({"expected_version": "No se envía en una creación."})
        return data


class MilkingUpdateCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["MILKING_UPDATE"], default="MILKING_UPDATE")
    expected_version = serializers.IntegerField(min_value=1)
    payload = MilkingUpdatePayload()


class MilkingSerializer(serializers.Serializer):
    replaces_id = serializers.UUIDField(allow_null=True)
    voided_at = serializers.DateTimeField(allow_null=True)
    lot_id = serializers.UUIDField(allow_null=True)
    id = serializers.UUIDField()
    production_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    center_id = serializers.UUIDField()
    responsible_id = serializers.UUIDField()
    date = serializers.DateField()
    turn_id = serializers.UUIDField()
    state = serializers.ChoiceField(choices=["BORRADOR", "CONFIRMADA", "ANULADA"])
    lock_version = serializers.IntegerField()
    version_id = serializers.UUIDField()
    version_number = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    details = CowDetail(many=True)
    complete = serializers.BooleanField()
    capabilities = serializers.ListField(child=serializers.CharField())


class MilkingReceipt(OperationResultSerializer):
    result = MilkingSerializer()


class MilkingConfirmPayload(StrictSerializer):
    version_id = serializers.UUIDField()
    lot_id = serializers.UUIDField()


class MilkingConfirmCommand(EnvelopeSerializer):
    type = serializers.ChoiceField(choices=["MILKING_CONFIRM"], default="MILKING_CONFIRM")
    expected_version = serializers.IntegerField(min_value=1)
    payload = MilkingConfirmPayload()
