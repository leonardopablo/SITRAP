from rest_framework import serializers

from apps.common.serializers import StrictSerializer
from apps.sync.serializers import EnvelopeSerializer

from .models import CATEGORIES, QUALITIES, Pen


class BucketInput(StrictSerializer):
    occupation_id = serializers.UUIDField(required=False)
    pen_id = serializers.UUIDField(required=False)
    category = serializers.ChoiceField(choices=CATEGORIES)
    quality = serializers.ChoiceField(choices=QUALITIES, default="SIN_CLASIFICAR")
    quantity = serializers.IntegerField(min_value=0, max_value=1000000)


class LotInput(StrictSerializer):
    provenance = serializers.CharField(max_length=240)
    born_from = serializers.DateField(required=False, allow_null=True)
    born_until = serializers.DateField(required=False, allow_null=True)
    installed_on = serializers.DateField(required=False, allow_null=True)


class BasePayload(StrictSerializer):
    date = serializers.DateField()
    reason = serializers.CharField(max_length=500)


class OpeningGroupInput(StrictSerializer):
    lot = LotInput()
    items = BucketInput(many=True, allow_empty=False, max_length=100)


class OpeningPayload(BasePayload):
    pen_id = serializers.UUIDField()
    lot = LotInput(required=False)
    items = BucketInput(many=True, allow_empty=False, max_length=100, required=False)
    groups = OpeningGroupInput(many=True, allow_empty=False, max_length=100, required=False)

    def validate(self, data):
        if "groups" in data:
            if "lot" in data or "items" in data:
                raise serializers.ValidationError("Use grupos o lote/ítems, no ambos.")
        elif "lot" not in data or "items" not in data:
            raise serializers.ValidationError("Faltan lote e ítems de apertura.")
        return data


class BirthPayload(BasePayload):
    occupation_id = serializers.UUIDField()
    live = serializers.IntegerField(min_value=0, max_value=10000)
    stillborn = serializers.IntegerField(min_value=0, max_value=10000, default=0)


class DeathPayload(BasePayload):
    items = BucketInput(many=True, allow_empty=False, max_length=100)
    cause = serializers.CharField(max_length=240, default="desconocida")


class WeanPayload(BasePayload):
    occupation_id = serializers.UUIDField()
    quality = serializers.ChoiceField(choices=QUALITIES, default="SIN_CLASIFICAR")
    quantity = serializers.IntegerField(min_value=1, max_value=1000000)
    destinations = BucketInput(many=True, allow_empty=False, max_length=100)


class MovePayload(BasePayload):
    source_id = serializers.UUIDField()
    destination_id = serializers.UUIDField()
    items = BucketInput(many=True, allow_empty=False, max_length=100)


class TransferPayload(BasePayload):
    transfer_id = serializers.UUIDField()


class RedirectPayload(TransferPayload):
    destination_id = serializers.UUIDField()


class ReclassPayload(BasePayload):
    items = BucketInput(many=True, allow_empty=False, max_length=100)
    new_quality = serializers.ChoiceField(choices=QUALITIES)


class CountPayload(BasePayload):
    pen_id = serializers.UUIDField()
    items = BucketInput(many=True, max_length=1000)


class ReviewPayload(BasePayload):
    count_id = serializers.UUIDField()
    approve = serializers.BooleanField()


class DailyPayload(BasePayload):
    shed_id = serializers.UUIDField()


class ResolvePayload(BasePayload):
    alert_id = serializers.UUIDField()


class RefreshPayload(BasePayload):
    pass


class CompensatePayload(BasePayload):
    movement_id = serializers.UUIDField()


PAYLOADS = {
    "CUY_OPEN": OpeningPayload, "CUY_BIRTH": BirthPayload, "CUY_DEATH": DeathPayload,
    "CUY_WEAN": WeanPayload, "CUY_MOVE": MovePayload, "CUY_DISPATCH": MovePayload,
    "CUY_RECEIVE": TransferPayload, "CUY_REDIRECT": RedirectPayload,
    "CUY_RECLASS": ReclassPayload, "CUY_COUNT": CountPayload, "CUY_REVIEW": ReviewPayload,
    "CUY_CLOSE": DailyPayload, "CUY_REOPEN": DailyPayload, "CUY_RESOLVE": ResolvePayload,
    "CUY_ALERTS": RefreshPayload, "CUY_COMPENSATE": CompensatePayload,
}


def command_serializer(kind):
    return type(
        f"{kind.title().replace('_', '')}Command", (EnvelopeSerializer,),
        {"__module__": __name__, "type": serializers.ChoiceField(choices=[kind]),
         "payload": PAYLOADS[kind]()},
    )


COMMANDS = {kind: command_serializer(kind) for kind in PAYLOADS}


class ConfigInput(StrictSerializer):
    resource = serializers.ChoiceField(choices=["enable", "shed", "pen", "grant", "policy"])
    id = serializers.UUIDField()
    reason = serializers.CharField(max_length=500)
    center_id = serializers.UUIDField(required=False)
    shed_id = serializers.UUIDField(required=False)
    assignment_id = serializers.UUIDField(required=False)
    code = serializers.RegexField(r"^[A-Z0-9][A-Z0-9_-]{0,39}$", required=False)
    name = serializers.CharField(max_length=150, required=False)
    active = serializers.BooleanField(default=True)
    capacity = serializers.IntegerField(min_value=1, max_value=1000000, required=False)
    purpose = serializers.ChoiceField(choices=Pen.Purpose.choices, required=False)
    reproductive_months = serializers.IntegerField(min_value=1, max_value=60, required=False)
    minimum_weaned_per_female = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0, required=False)


class LotOutput(serializers.Serializer):
    id = serializers.UUIDField()
    provenance = serializers.CharField()
    parent_id = serializers.UUIDField(allow_null=True)
    source_occupation_id = serializers.UUIDField(allow_null=True)
    opened_on = serializers.DateField()
    born_from = serializers.DateField(allow_null=True)
    born_until = serializers.DateField(allow_null=True)
    installed_on = serializers.DateField(allow_null=True)
    age_days_min = serializers.IntegerField(allow_null=True)
    age_days_max = serializers.IntegerField(allow_null=True)
    rearing_days = serializers.IntegerField()
    reproductive_days = serializers.IntegerField(allow_null=True)


class BalanceOutput(serializers.Serializer):
    category = serializers.ChoiceField(choices=CATEGORIES)
    quality = serializers.ChoiceField(choices=QUALITIES)
    quantity = serializers.IntegerField()


class OccupationOutput(serializers.Serializer):
    id = serializers.UUIDField()
    started_on = serializers.DateField()
    closed_on = serializers.DateField(allow_null=True)
    lot = LotOutput()
    balances = BalanceOutput(many=True)


class PenOutput(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    shed_id = serializers.UUIDField()
    shed = serializers.CharField()
    center_id = serializers.UUIDField()
    center = serializers.CharField()
    capacity = serializers.IntegerField()
    purpose = serializers.ChoiceField(choices=Pen.Purpose.choices)
    active = serializers.BooleanField()
    population = serializers.IntegerField()
    totals = serializers.DictField(child=serializers.IntegerField())
    overcapacity = serializers.BooleanField()
    occupations = OccupationOutput(many=True)
    last_count = serializers.DateField(allow_null=True)
    last_close = serializers.DateField(allow_null=True)


class ShedOutput(serializers.Serializer):
    id = serializers.UUIDField()
    center_id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    active = serializers.BooleanField()


class ConfigOutput(serializers.Serializer):
    centers = serializers.ListField(child=serializers.DictField())
    enabled_centers = serializers.ListField(child=serializers.UUIDField())
    policies = serializers.ListField(child=serializers.DictField())
    grants = serializers.ListField(child=serializers.DictField())


class CuyQuery(StrictSerializer):
    pen_id = serializers.UUIDField(required=False)
    shed_id = serializers.UUIDField(required=False)
    center_id = serializers.UUIDField(required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    limit = serializers.IntegerField(min_value=1, max_value=200, default=50)
    offset = serializers.IntegerField(min_value=0, default=0)

    def validate(self, data):
        from django.utils import timezone

        start, end = data.get("start"), data.get("end")
        if start and end and ((end - start).days > 366 or end < start):
            raise serializers.ValidationError("Período máximo 366 días y orden cronológico.")
        if end and end > timezone.localdate():
            raise serializers.ValidationError("No se admiten períodos futuros.")
        return data


class CuyPage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    results = serializers.JSONField()


class PensPage(CuyPage):
    results = PenOutput(many=True)


class ShedsPage(CuyPage):
    results = ShedOutput(many=True)


class DashboardSerializer(serializers.Serializer):
    updated_at = serializers.DateTimeField()
    population = serializers.IntegerField()
    in_transit = serializers.IntegerField()
    pens = PenOutput(many=True)
    indicators = serializers.JSONField()
    alerts = serializers.JSONField()
