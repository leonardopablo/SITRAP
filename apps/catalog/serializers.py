from decimal import Decimal

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


class UnitInput(StrictSerializer):
    code = serializers.ChoiceField(choices=["L", "KG", "UN"])
    name = serializers.CharField(max_length=50)


class PresentationInput(StrictSerializer):
    id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    name = serializers.CharField(max_length=100)
    content_base = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0.001")
    )
    allows_fraction = serializers.BooleanField(default=False)
    active = serializers.BooleanField(default=True)


class SpeciesInput(StrictSerializer):
    id = serializers.UUIDField()
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=100)
    active = serializers.BooleanField(default=True)


class TurnInput(SpeciesInput):
    pass
