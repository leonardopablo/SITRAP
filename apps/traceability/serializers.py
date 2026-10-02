from rest_framework import serializers


class LotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    production_id = serializers.UUIDField()
    center_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    responsible_id = serializers.UUIDField()
    date = serializers.DateField()
    turn_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)
    production_state = serializers.ChoiceField(choices=["BORRADOR", "CONFIRMADA", "ANULADA"])
    created_at = serializers.DateTimeField()


class LineSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    lot_id = serializers.UUIDField()
    presentation_id = serializers.UUIDField()
    units = serializers.DecimalField(max_digits=14, decimal_places=3)
    content_base_snapshot = serializers.DecimalField(max_digits=14, decimal_places=3)
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3)


class TransferVersionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.IntegerField()
    origin_id = serializers.UUIDField()
    destination_id = serializers.UUIDField()
    emitter_id = serializers.UUIDField()
    driver_id = serializers.UUIDField()
    receiver_id = serializers.UUIDField()
    state = serializers.CharField()
    reason = serializers.CharField()
    published_at = serializers.DateTimeField(allow_null=True)
    lines = LineSerializer(many=True)


class TransferSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    creator_id = serializers.UUIDField()
    state = serializers.ChoiceField(
        choices=["BORRADOR", "PENDIENTE_RECOGIDA", "EN_CAMINO", "RECIBIDO", "CANCELADO"]
    )
    lock_version = serializers.IntegerField()
    version_id = serializers.UUIDField(allow_null=True)
    current_version = TransferVersionSerializer(allow_null=True)
    versions = TransferVersionSerializer(many=True)
    capabilities = serializers.ListField(child=serializers.CharField())


class TimelineSerializer(serializers.Serializer):
    type = serializers.CharField()
    at = serializers.DateTimeField()
    registered_at = serializers.DateTimeField(required=False)
    version_id = serializers.UUIDField()
    actor_id = serializers.UUIDField()
