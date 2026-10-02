from rest_framework import serializers

from apps.common.serializers import StrictSerializer


class LocationInput(StrictSerializer):
    id = serializers.UUIDField()
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(choices=["CENTRO", "PUNTO_VENTA"])
    active = serializers.BooleanField(default=True)


class ProductInput(StrictSerializer):
    id = serializers.UUIDField()
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=150)
    unit_id = serializers.ChoiceField(choices=["L", "KG", "UN"])
    active = serializers.BooleanField(default=True)


class CenterProductInput(StrictSerializer):
    id = serializers.UUIDField()
    center_id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    enabled = serializers.BooleanField(default=True)
