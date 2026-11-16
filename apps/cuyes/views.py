from urllib.parse import urlencode

from django.db.models import Q
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import require_admin
from apps.common.errors import ErrorSerializer
from apps.sync.commands import dispatch
from apps.sync.serializers import OperationResultSerializer

from .access import destination_pens, pens_for, sheds_for
from .models import Alert, AlertPolicy, DailyReport, Movement, PhysicalCount, ShedGrant
from .reports import dashboard, ledger_data, pen_data, scoped_transfers, transfer_data
from .serializers import (
    COMMANDS,
    ConfigInput,
    ConfigOutput,
    CuyPage,
    CuyQuery,
    DashboardSerializer,
    PenOutput,
    PensPage,
    ShedsPage,
)
from .services import configure, get

ERRORS = {401: ErrorSerializer, 403: ErrorSerializer, 409: ErrorSerializer, 422: ErrorSerializer}


def parameters(request):
    serializer = CuyQuery(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def page(request, query, serialize):
    p = parameters(request)
    offset, limit = p["offset"], p["limit"]
    count = query.count()
    next_query = request.query_params.dict()
    next_query["offset"] = offset + limit
    return Response({
        "count": count, "next": f"{request.path}?{urlencode(next_query)}" if offset + limit < count else None,
        "results": [serialize(obj) for obj in query[offset:offset + limit]],
    })


def filtered_pens(actor, p):
    query = pens_for(actor)
    for param, field in [("pen_id", "id"), ("shed_id", "shed_id"), ("center_id", "shed__center_id")]:
        if p.get(param):
            query = query.filter(**{field: p[param]})
    return query


class ConfigView(APIView):
    @extend_schema(responses={200: ConfigOutput, **ERRORS})
    def get(self, request):
        require_admin(request.user)
        from apps.catalog.models import Location

        from .access import enabled_centers

        return Response({
            "centers": list(Location.objects.filter(kind="CENTRO", active=True).values("id", "code", "name")),
            "enabled_centers": list(enabled_centers()),
            "policies": list(AlertPolicy.objects.values()),
            "grants": list(ShedGrant.objects.values()),
        })

    @extend_schema(request=ConfigInput, responses={200: dict, **ERRORS})
    def post(self, request):
        s = ConfigInput(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(configure(request.user, s.validated_data))


class ShedsView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: ShedsPage, **ERRORS})
    def get(self, request):
        p = parameters(request)
        query = sheds_for(request.user)
        if p.get("center_id"):
            query = query.filter(center_id=p["center_id"])
        return page(request, query.order_by("code", "id"), lambda s: {
            "id": s.id, "center_id": s.center_id, "code": s.code, "name": s.name, "active": s.active,
        })


class PensView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: PensPage, **ERRORS})
    def get(self, request):
        return page(request, filtered_pens(request.user, parameters(request)).order_by("code"), pen_data)


class PenDetailView(APIView):
    @extend_schema(operation_id="cuyes_pen_detail", responses={200: PenOutput, **ERRORS})
    def get(self, request, pk):
        return Response(pen_data(get(pens_for(request.user), pk)))


class DestinationsView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: CuyPage, **ERRORS})
    def get(self, request):
        return page(request, destination_pens(request.user).order_by("code"), lambda p: {
            "id": p.id, "code": p.code, "shed_id": p.shed_id, "center_id": p.shed.center_id,
            "purpose": p.purpose, "capacity": p.capacity,
        })


class KardexView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: CuyPage, **ERRORS})
    def get(self, request):
        p = parameters(request)
        pens = filtered_pens(request.user, p)
        from .models import Occupation

        occupation_ids = [str(pk) for pk in Occupation.objects.filter(pen__in=pens).values_list("id", flat=True)]
        query = Movement.objects.filter(
            Q(lines__occupation__pen__in=pens)
            | Q(kind="BIRTH", metadata__occupation_id__in=occupation_ids),
        ).distinct().select_related("actor")
        if p.get("start"):
            query = query.filter(date__gte=p["start"])
        if p.get("end"):
            query = query.filter(date__lte=p["end"])
        return page(request, query.order_by("-registered_at", "-id"), lambda m: ledger_data(m, pens))


class TransfersView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: CuyPage, **ERRORS})
    def get(self, request):
        p = parameters(request)
        query = scoped_transfers(request.user)
        pens = filtered_pens(request.user, p)
        query = query.filter(Q(source__in=pens) | Q(destination__in=pens)).distinct()
        return page(request, query.order_by("-dispatched_at", "-id"), transfer_data)


class CountsView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: CuyPage, **ERRORS})
    def get(self, request):
        query = PhysicalCount.objects.filter(pen__in=filtered_pens(request.user, parameters(request)))
        return page(request, query.order_by("-registered_at", "-id"), lambda c: {
            "id": c.id, "pen_id": c.pen_id, "date": c.date, "opening": c.opening, "state": c.state,
            "author_id": c.author_id, "reviewed_by_id": c.reviewed_by_id, "reason": c.reason,
            "details": [dict(occupation_id=d.occupation_id, category=d.category, quality=d.quality,
                             expected=d.expected, observed=d.observed, difference=d.difference) for d in c.details.all()],
        })


class ReportsView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: CuyPage, **ERRORS})
    def get(self, request):
        p = parameters(request)
        query = DailyReport.objects.filter(shed__in=sheds_for(request.user))
        if p.get("shed_id"):
            query = query.filter(shed_id=p["shed_id"])
        return page(request, query.order_by("-date", "-id"), lambda r: {
            "id": r.id, "shed_id": r.shed_id, "date": r.date, "state": r.state,
            "responsible_id": r.responsible_id, "closed_at": r.closed_at,
            "revisions": list(r.revisions.order_by("registered_at").values("action", "actor_id", "reason", "registered_at")),
        })


class DashboardView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: DashboardSerializer, **ERRORS})
    def get(self, request):
        return Response(dashboard(request.user, parameters(request)))


class AlertsView(APIView):
    @extend_schema(parameters=[CuyQuery], responses={200: CuyPage, **ERRORS})
    def get(self, request):
        query = Alert.objects.filter(pen__in=filtered_pens(request.user, parameters(request)))
        return page(request, query.order_by("-created_at", "-id"), lambda a: {
            "id": a.id, "pen_id": a.pen_id, "kind": a.kind, "text": a.text,
            "resolved_at": a.resolved_at, "reason": a.reason,
        })


class CommandsView(APIView):
    @extend_schema(
        request=PolymorphicProxySerializer(
            component_name="CuyCommand", serializers=COMMANDS, resource_type_field_name="type",
        ),
        responses={200: OperationResultSerializer, **ERRORS},
    )
    def post(self, request):
        from .services import fail

        if request.data.get("type") not in COMMANDS:
            fail("Comando de Cuyes no válido.", "VALIDATION_ERROR", 422)
        body, status = dispatch(request.user, request.data)
        return Response(body, status=status)
