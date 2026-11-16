from decimal import Decimal

from rest_framework import serializers

from apps.common.serializers import StrictSerializer
from apps.sync.serializers import EnvelopeSerializer

from .models import QUALITIES


class CommercialBase(StrictSerializer):
    reason = serializers.CharField(max_length=500)


class ComponentInput(StrictSerializer):
    category = serializers.ChoiceField(choices=["MACHO", "HEMBRA"])
    quality = serializers.ChoiceField(choices=QUALITIES)
    quantity = serializers.IntegerField(min_value=1, max_value=100000)


class ModuleInput(CommercialBase):
    id = serializers.UUIDField()
    name = serializers.CharField(max_length=150)
    active = serializers.BooleanField(default=True)
    components = ComponentInput(many=True, allow_empty=False, max_length=20)


class SaleItemInput(StrictSerializer):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=["UNIDAD", "PESO", "MODULO"])
    units = serializers.IntegerField(min_value=1, max_value=100000)
    category = serializers.ChoiceField(choices=["MACHO", "HEMBRA"], required=False)
    quality = serializers.ChoiceField(choices=QUALITIES, required=False)
    module_id = serializers.UUIDField(required=False)
    weight_kg = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"), required=False)
    weight_basis = serializers.ChoiceField(choices=["VIVO", "BENEFICIADO"], required=False)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class CreateSale(CommercialBase):
    center_id = serializers.UUIDField()
    client_name = serializers.CharField(max_length=150)
    client_reference = serializers.CharField(max_length=100, default="", allow_blank=True)
    client_contact = serializers.CharField(max_length=100, default="", allow_blank=True)
    mode = serializers.ChoiceField(choices=["DIRECTO", "PUNTO"])
    point_id = serializers.UUIDField(required=False, allow_null=True)
    currency = serializers.ChoiceField(choices=["PEN", "USD"], default="PEN")
    items = SaleItemInput(many=True, allow_empty=False, max_length=50)


class PaySale(CommercialBase):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.ChoiceField(choices=["PEN", "USD"])
    method = serializers.CharField(max_length=60)
    reference = serializers.CharField(max_length=150)
    evidence_id = serializers.UUIDField()


class DriverSale(CommercialBase):
    driver_id = serializers.UUIDField()


class SelectionInput(ComponentInput):
    line_id = serializers.UUIDField()
    occupation_id = serializers.UUIDField()


class PrepareSale(CommercialBase):
    shed_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False, max_length=100)
    items = SelectionInput(many=True, max_length=1000)


class ConformSale(CommercialBase):
    preparation_id = serializers.UUIDField()
    round = serializers.IntegerField(min_value=1)
    shed_ids = serializers.ListField(child=serializers.UUIDField(), default=list, max_length=100)


class ArrivalSale(CommercialBase):
    delivered_to_client = serializers.BooleanField()
    physical_responsible = serializers.CharField(max_length=150)
    reference = serializers.CharField(max_length=150)


class CollectSale(CommercialBase):
    physical_responsible = serializers.CharField(max_length=150)
    reference = serializers.CharField(max_length=150)


class CancelSale(CommercialBase):
    payment_treatment = serializers.CharField(max_length=500, required=False)


class ProposalItem(StrictSerializer):
    line_id = serializers.UUIDField()
    units = serializers.IntegerField(min_value=1, max_value=100000)
    weight_kg = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"), required=False)


class ProposeSale(CommercialBase):
    items = ProposalItem(many=True, allow_empty=False, max_length=50)


class ReviewProposal(CommercialBase):
    proposal_id = serializers.UUIDField()
    approve = serializers.BooleanField()


class WeighSale(CommercialBase):
    line_id = serializers.UUIDField()
    weight_kg = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))


class FinanceSale(CommercialBase):
    treatment = serializers.ChoiceField(choices=["COBRO_ADICIONAL", "DEVOLUCION", "ABSORBIDO"])
    reference = serializers.CharField(max_length=150)
    evidence_id = serializers.UUIDField(required=False)


SALE_PAYLOADS = {
    "SALE_CREATE": CreateSale, "SALE_CONFIRM": CommercialBase,
    "SALE_REJECT": CommercialBase, "SALE_PROPOSE": ProposeSale,
    "SALE_PROPOSAL_REVIEW": ReviewProposal, "SALE_PAY": PaySale,
    "SALE_DRIVER": DriverSale, "SALE_SELECT": PrepareSale,
    "SALE_ORIGIN": ConformSale, "SALE_PICKUP": ConformSale,
    "SALE_DEPART": CommercialBase, "SALE_ARRIVE": ArrivalSale,
    "SALE_COLLECT": CollectSale, "SALE_CANCEL": CancelSale,
    "SALE_WEIGH": WeighSale, "SALE_FINANCE": FinanceSale,
    "SALE_RESOLVE_STOCK": CommercialBase,
}


SALE_COMMANDS = {
    kind: type(
        f"{kind.title().replace('_', '')}Command", (EnvelopeSerializer,),
        {"__module__": __name__, "type": serializers.ChoiceField(choices=[kind]), "payload": payload()},
    )
    for kind, payload in SALE_PAYLOADS.items()
}


class PinGenerationInput(CommercialBase):
    expected_version = serializers.IntegerField(min_value=1)


class PinDeliveryInput(CommercialBase):
    event_id = serializers.UUIDField()
    device_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=1)
    pin = serializers.RegexField(r"^\d{8}$", write_only=True, trim_whitespace=False)
    physical_responsible = serializers.CharField(max_length=150)
    reference = serializers.CharField(max_length=150)


class PinGenerationOutput(serializers.Serializer):
    pin = serializers.CharField()
    version = serializers.IntegerField()
    message = serializers.CharField()


class VoucherInput(StrictSerializer):
    id = serializers.UUIDField()
    file = serializers.FileField()


class VoucherOutput(serializers.Serializer):
    id = serializers.UUIDField()
    size = serializers.IntegerField()
    content_type = serializers.CharField()


class SalesQuery(StrictSerializer):
    workspace = serializers.ChoiceField(choices=["ADMIN", "GALPONERO", "TRANSPORTE"], required=False)
    center_id = serializers.UUIDField(required=False)
    state = serializers.CharField(max_length=20, required=False)
    limit = serializers.IntegerField(min_value=1, max_value=200, default=50)
    offset = serializers.IntegerField(min_value=0, default=0)


class SaleOutput(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    center_id = serializers.UUIDField()
    mode = serializers.CharField()
    state = serializers.CharField()
    display_state = serializers.CharField()
    stage = serializers.IntegerField()
    version = serializers.IntegerField()
    shortage = serializers.BooleanField()
    financial_hold = serializers.BooleanField()
    ready_to_dispatch = serializers.BooleanField()
    client = serializers.DictField()
    lines = serializers.ListField(child=serializers.DictField())
    reservation = serializers.JSONField(allow_null=True)
    preparation = serializers.JSONField(allow_null=True)
    dispatch = serializers.JSONField(allow_null=True)
    deliveries = serializers.ListField(child=serializers.DictField())
    actions = serializers.ListField(child=serializers.CharField())
    total = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    currency = serializers.CharField(required=False)
    reason = serializers.CharField(required=False)


class SalePage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    results = SaleOutput(many=True)


class ObjectPage(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    results = serializers.ListField(child=serializers.DictField())


class SalesOptionsOutput(serializers.Serializer):
    centers = serializers.ListField(child=serializers.DictField())
    points = serializers.ListField(child=serializers.DictField())
    drivers = serializers.ListField(child=serializers.DictField())
