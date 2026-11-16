from django.conf import settings
from django.db import models
from django.db.models import Q

from .models import Identified


class BreedingModule(Identified):
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)


class ModuleComponent(Identified):
    module = models.ForeignKey(BreedingModule, related_name="components", on_delete=models.PROTECT)
    category = models.CharField(max_length=8, choices=[("MACHO", "Macho"), ("HEMBRA", "Hembra")])
    quality = models.CharField(max_length=16)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["module", "category", "quality"], name="sale_module_bucket"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="sale_component_positive"),
            models.CheckConstraint(condition=Q(category__in=["MACHO", "HEMBRA"]), name="sale_component_category"),
            models.CheckConstraint(condition=Q(quality__in=["A", "B", "C", "SIN_CLASIFICAR"]), name="sale_component_quality"),
        ]


class SaleOrder(Identified):
    class State(models.TextChoices):
        SOLICITADO = "SOLICITADO"
        AJUSTE_PENDIENTE = "AJUSTE_PENDIENTE"
        RESERVADO = "RESERVADO"
        PAGADO = "PAGADO"
        EN_PREPARACION = "EN_PREPARACION"
        EN_RUTA = "EN_RUTA"
        EN_PUNTO = "EN_PUNTO"
        ENTREGADO = "ENTREGADO"
        RECHAZADO = "RECHAZADO"
        CANCELADO = "CANCELADO"
        VENCIDO = "VENCIDO"

    code = models.CharField(max_length=40, unique=True)
    center = models.ForeignKey("catalog.Location", on_delete=models.PROTECT, related_name="+")
    client_name = models.CharField(max_length=150)
    client_reference = models.CharField(max_length=100, blank=True)
    client_contact = models.CharField(max_length=100, blank=True)
    mode = models.CharField(max_length=8, choices=[("DIRECTO", "Recojo directo"), ("PUNTO", "Punto de venta")])
    point = models.ForeignKey("catalog.Location", null=True, on_delete=models.PROTECT, related_name="+")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    currency = models.CharField(max_length=3, default="PEN")
    state = models.CharField(max_length=20, choices=State.choices, default=State.SOLICITADO)
    version = models.PositiveIntegerField(default=1)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    approved_total = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    financial_hold = models.BooleanField(default=False)
    shortage = models.BooleanField(default=False)
    preparation = models.ForeignKey("SalePreparation", null=True, on_delete=models.PROTECT, related_name="+")
    confirmation_round = models.PositiveIntegerField(default=1)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    pin_hash = models.CharField(max_length=256, blank=True)
    pin_generation = models.PositiveIntegerField(default=0)
    pin_failures = models.PositiveIntegerField(default=0)
    pin_generated_at = models.DateTimeField(null=True)
    pin_consumed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(total__gte=0), name="sale_total_nonnegative"),
            models.CheckConstraint(condition=Q(mode="DIRECTO", point__isnull=True) | Q(mode="PUNTO", point__isnull=False), name="sale_mode_point"),
            models.CheckConstraint(condition=Q(mode="PUNTO") | Q(driver__isnull=True), name="sale_direct_no_driver"),
            models.CheckConstraint(condition=Q(currency__in=["PEN", "USD"]), name="sale_currency"),
            models.CheckConstraint(condition=Q(state__in=[
                "SOLICITADO", "AJUSTE_PENDIENTE", "RESERVADO", "PAGADO", "EN_PREPARACION",
                "EN_RUTA", "EN_PUNTO", "ENTREGADO", "RECHAZADO", "CANCELADO", "VENCIDO",
            ]), name="sale_order_state"),
        ]


class SaleLine(Identified):
    order = models.ForeignKey(SaleOrder, related_name="lines", on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=[("UNIDAD", "Unidad"), ("PESO", "Peso"), ("MODULO", "Módulo")])
    units = models.PositiveIntegerField()
    animal_count = models.PositiveIntegerField()
    category = models.CharField(max_length=8, blank=True)
    quality = models.CharField(max_length=16, blank=True)
    module = models.ForeignKey(BreedingModule, null=True, on_delete=models.PROTECT)
    recipe = models.JSONField(default=list)
    billing_unit = models.CharField(max_length=6)
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True)
    weight_basis = models.CharField(max_length=12, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(units__gt=0, animal_count__gt=0, unit_price__gt=0, total__gt=0), name="sale_line_positive"),
            models.CheckConstraint(condition=Q(kind__in=["UNIDAD", "PESO", "MODULO"]), name="sale_line_kind"),
            models.CheckConstraint(condition=Q(kind="PESO", weight_kg__gt=0, billing_unit="KG") | Q(kind__in=["UNIDAD", "MODULO"], weight_kg__isnull=True, billing_unit="UN"), name="sale_line_weight"),
        ]


class SaleReservation(Identified):
    order = models.ForeignKey(SaleOrder, related_name="reservations", on_delete=models.PROTECT)
    center = models.ForeignKey("catalog.Location", on_delete=models.PROTECT)
    state = models.CharField(max_length=10, default="IMPAGA")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True)
    consumed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order"], condition=Q(state__in=["IMPAGA", "PAGADA"]), name="sale_active_reservation"),
            models.CheckConstraint(condition=Q(state__in=["IMPAGA", "PAGADA", "VENCIDA", "LIBERADA", "CONSUMIDA"]), name="sale_reservation_state"),
        ]
        indexes = [models.Index(fields=["state", "expires_at"])]


class ReservationDetail(Identified):
    reservation = models.ForeignKey(SaleReservation, related_name="details", on_delete=models.PROTECT)
    category = models.CharField(max_length=8)
    quality = models.CharField(max_length=16)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reservation", "category", "quality"], name="sale_reserved_bucket"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="sale_reserved_positive"),
        ]


class PaymentEvidence(Identified):
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    storage_name = models.CharField(max_length=240, unique=True)
    digest = models.CharField(max_length=64)
    content_type = models.CharField(max_length=32)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class SalePayment(Identified):
    order = models.OneToOneField(SaleOrder, related_name="payment", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3)
    method = models.CharField(max_length=60)
    reference = models.CharField(max_length=150)
    evidence = models.OneToOneField(PaymentEvidence, on_delete=models.PROTECT)
    validated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    validated_at = models.DateTimeField(auto_now_add=True)
    operation = models.OneToOneField("sync.SyncOperation", on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="sale_payment_positive")]


class SaleFinancialReview(Identified):
    order = models.ForeignKey(SaleOrder, related_name="financial_reviews", on_delete=models.PROTECT)
    previous_total = models.DecimalField(max_digits=14, decimal_places=2)
    new_total = models.DecimalField(max_digits=14, decimal_places=2)
    difference = models.DecimalField(max_digits=14, decimal_places=2)
    treatment = models.CharField(max_length=24)
    evidence = models.ForeignKey(PaymentEvidence, null=True, on_delete=models.PROTECT)
    reference = models.CharField(max_length=500)
    reason = models.CharField(max_length=500)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registered_at = models.DateTimeField(auto_now_add=True)


class SaleProposal(Identified):
    order = models.ForeignKey(SaleOrder, related_name="proposals", on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    items = models.JSONField()
    reason = models.CharField(max_length=500)
    state = models.CharField(max_length=10, default="PENDIENTE")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class SalePreparation(Identified):
    order = models.ForeignKey(SaleOrder, related_name="preparations", on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class DispatchSelection(Identified):
    preparation = models.ForeignKey(SalePreparation, related_name="selections", on_delete=models.PROTECT)
    line = models.ForeignKey(SaleLine, on_delete=models.PROTECT)
    occupation = models.ForeignKey("cuyes.Occupation", on_delete=models.PROTECT)
    category = models.CharField(max_length=8)
    quality = models.CharField(max_length=16)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["preparation", "line", "occupation", "category", "quality"], name="sale_selection_bucket"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="sale_selection_positive"),
        ]


class SaleConformity(Identified):
    preparation = models.ForeignKey(SalePreparation, related_name="conformities", on_delete=models.PROTECT)
    round = models.PositiveIntegerField()
    stage = models.CharField(max_length=12)
    shed = models.ForeignKey("cuyes.Shed", null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["preparation", "round", "shed"], condition=Q(stage="GALPONERO"), name="sale_shed_conformity"),
            models.UniqueConstraint(fields=["preparation", "round"], condition=Q(stage="CONDUCTOR"), name="sale_driver_conformity"),
            models.CheckConstraint(condition=Q(stage="GALPONERO", shed__isnull=False) | Q(stage="CONDUCTOR", shed__isnull=True), name="sale_conformity_scope"),
        ]


class SaleDispatch(Identified):
    order = models.OneToOneField(SaleOrder, related_name="dispatch", on_delete=models.PROTECT)
    movement = models.OneToOneField("cuyes.Movement", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    preparation = models.OneToOneField(SalePreparation, on_delete=models.PROTECT)
    departed_at = models.DateTimeField(auto_now_add=True)


class SaleDispatchDetail(Identified):
    dispatch = models.ForeignKey(SaleDispatch, related_name="details", on_delete=models.PROTECT)
    line = models.ForeignKey(SaleLine, on_delete=models.PROTECT)
    occupation = models.ForeignKey("cuyes.Occupation", on_delete=models.PROTECT)
    category = models.CharField(max_length=8)
    quality = models.CharField(max_length=16)
    quantity = models.PositiveIntegerField()
    snapshot = models.JSONField()


class SaleDelivery(Identified):
    order = models.ForeignKey(SaleOrder, related_name="deliveries", on_delete=models.PROTECT)
    stage = models.CharField(max_length=16)
    registered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    physical_responsible = models.CharField(max_length=150)
    reference = models.CharField(max_length=150)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "stage"], name="sale_delivery_once")]


class SaleRevision(Identified):
    order = models.ForeignKey(SaleOrder, related_name="revisions", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    reason = models.CharField(max_length=500)
    snapshot = models.JSONField()
    registered_at = models.DateTimeField(auto_now_add=True)
