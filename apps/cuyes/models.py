import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Identified(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Shed(Identified):
    center = models.ForeignKey("catalog.Location", on_delete=models.PROTECT)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["center", "code"], name="cuy_shed_code")]


class Pen(Identified):
    class Purpose(models.TextChoices):
        MATERNIDAD = "MATERNIDAD", "Empadre / Maternidad"
        RECRIA_MACHOS = "RECRIA_MACHOS", "Recría Machos"
        RECRIA_HEMBRAS = "RECRIA_HEMBRAS", "Recría Hembras"
        ACABADO = "ACABADO", "Venta / Acabado"
        ENFERMERIA = "ENFERMERIA", "Enfermería / Descarte"

    shed = models.ForeignKey(Shed, on_delete=models.PROTECT)
    code = models.CharField(max_length=40, unique=True)
    capacity = models.PositiveIntegerField()
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(capacity__gt=0), name="cuy_capacity_positive"),
            models.CheckConstraint(condition=Q(purpose__in=[
                "MATERNIDAD", "RECRIA_MACHOS", "RECRIA_HEMBRAS", "ACABADO", "ENFERMERIA",
            ]), name="cuy_purpose_valid"),
        ]


class ShedGrant(Identified):
    assignment = models.ForeignKey("accounts.RoleAssignment", on_delete=models.PROTECT)
    shed = models.ForeignKey(Shed, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment", "shed"], name="cuy_shed_grant")]


class CuyLot(Identified):
    provenance = models.CharField(max_length=240)
    opened_on = models.DateField()
    born_from = models.DateField(null=True)
    born_until = models.DateField(null=True)
    installed_on = models.DateField(null=True)
    parent = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    source_occupation = models.ForeignKey("Occupation", null=True, on_delete=models.PROTECT, related_name="derived_lots")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(born_until__isnull=True) | Q(born_until__gte=models.F("born_from")), name="cuy_birth_interval"),
        ]


class Occupation(Identified):
    lot = models.ForeignKey(CuyLot, on_delete=models.PROTECT)
    pen = models.ForeignKey(Pen, on_delete=models.PROTECT)
    started_on = models.DateField()
    closed_on = models.DateField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lot", "pen"], condition=Q(closed_on__isnull=True), name="cuy_open_occupation"),
        ]


CATEGORIES = ["MACHO", "HEMBRA", "LACTANTE"]
QUALITIES = ["A", "B", "C", "SIN_CLASIFICAR"]


class Balance(Identified):
    occupation = models.ForeignKey(Occupation, on_delete=models.PROTECT, related_name="balances")
    category = models.CharField(max_length=8, choices=[(v, v) for v in CATEGORIES])
    quality = models.CharField(max_length=16, choices=[(v, v) for v in QUALITIES])
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["occupation", "category", "quality"], name="cuy_balance_bucket"),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="cuy_balance_nonnegative"),
            models.CheckConstraint(condition=Q(category__in=CATEGORIES), name="cuy_category_valid"),
            models.CheckConstraint(condition=Q(quality__in=QUALITIES), name="cuy_quality_valid"),
        ]


class Movement(Identified):
    operation = models.OneToOneField("sync.SyncOperation", on_delete=models.PROTECT)
    kind = models.CharField(max_length=24)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    date = models.DateField()
    registered_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=500)
    metadata = models.JSONField(default=dict)
    compensates = models.ForeignKey("self", null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["compensates"], condition=Q(compensates__isnull=False), name="cuy_one_compensation"),
        ]
        indexes = [models.Index(fields=["date", "kind"])]


class LedgerLine(Identified):
    movement = models.ForeignKey(Movement, related_name="lines", on_delete=models.PROTECT)
    occupation = models.ForeignKey(Occupation, on_delete=models.PROTECT)
    category = models.CharField(max_length=8)
    quality = models.CharField(max_length=16)
    delta = models.IntegerField()
    # Immutable labels/age references, not a join against today's renamed catalog.
    snapshot = models.JSONField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(delta=0), name="cuy_line_nonzero"),
            models.CheckConstraint(condition=Q(category__in=CATEGORIES), name="cuy_line_category"),
            models.CheckConstraint(condition=Q(quality__in=QUALITIES), name="cuy_line_quality"),
        ]
        indexes = [models.Index(fields=["occupation", "category", "quality"])]


class Transfer(Identified):
    source = models.ForeignKey(Pen, on_delete=models.PROTECT, related_name="outgoing")
    destination = models.ForeignKey(Pen, on_delete=models.PROTECT, related_name="incoming")
    dispatched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    dispatched_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True)
    state = models.CharField(max_length=12, default="EN_TRANSITO")
    items = models.JSONField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(state__in=["EN_TRANSITO", "RECIBIDO"]), name="cuy_transit_state"),
            models.CheckConstraint(condition=~Q(source=models.F("destination")), name="cuy_different_pens"),
        ]


class PhysicalCount(Identified):
    pen = models.ForeignKey(Pen, on_delete=models.PROTECT)
    date = models.DateField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    opening = models.BooleanField(default=False)
    registered_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=16, default="PENDIENTE")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True)
    reason = models.CharField(max_length=500, blank=True)


class CountDetail(Identified):
    count = models.ForeignKey(PhysicalCount, related_name="details", on_delete=models.PROTECT)
    occupation = models.ForeignKey(Occupation, on_delete=models.PROTECT)
    category = models.CharField(max_length=8)
    quality = models.CharField(max_length=16)
    expected = models.PositiveIntegerField()
    observed = models.PositiveIntegerField()

    @property
    def difference(self):
        return self.observed - self.expected

    class Meta:
        constraints = [models.UniqueConstraint(fields=["count", "occupation", "category", "quality"], name="cuy_count_bucket")]


class DailyReport(Identified):
    shed = models.ForeignKey(Shed, on_delete=models.PROTECT)
    date = models.DateField()
    state = models.CharField(max_length=8, default="ABIERTO")
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    closed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["shed", "date"], name="cuy_daily_unique"),
            models.CheckConstraint(condition=Q(state__in=["ABIERTO", "CERRADO"]), name="cuy_daily_state"),
        ]


class DailyRevision(Identified):
    report = models.ForeignKey(DailyReport, related_name="revisions", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=12)
    reason = models.CharField(max_length=500)
    registered_at = models.DateTimeField(auto_now_add=True)


class AlertPolicy(Identified):
    center = models.OneToOneField("catalog.Location", on_delete=models.PROTECT)
    reproductive_months = models.PositiveIntegerField(default=13)
    minimum_weaned_per_female = models.DecimalField(max_digits=6, decimal_places=2, default=1)


class Alert(Identified):
    pen = models.ForeignKey(Pen, on_delete=models.PROTECT)
    key = models.CharField(max_length=160, unique=True)
    kind = models.CharField(max_length=24)
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    reason = models.CharField(max_length=500, blank=True)


# Register the commercial extension in the same app; it uses the existing Kardex.
from .sales_models import (  # noqa: E402, F401
    BreedingModule,
    DispatchSelection,
    ModuleComponent,
    PaymentEvidence,
    ReservationDetail,
    SaleConformity,
    SaleDelivery,
    SaleDispatch,
    SaleDispatchDetail,
    SaleFinancialReview,
    SaleLine,
    SaleOrder,
    SalePayment,
    SalePreparation,
    SaleProposal,
    SaleReservation,
    SaleRevision,
)
