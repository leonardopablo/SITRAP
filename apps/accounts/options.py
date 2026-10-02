from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import is_admin, require_role
from apps.accounts.models import RoleAssignment, User
from apps.catalog.models import Location
from apps.common.errors import DomainError, ErrorSerializer
from apps.common.serializers import StrictSerializer


def assignable_users(role, location_id):
    now = timezone.now()
    assignments = RoleAssignment.objects.filter(
        role_id=role,
        scope="UBICACION",
        location_id=location_id,
        location__active=True,
        user__is_active=True,
        starts_at__lte=now,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
    return User.objects.filter(pk__in=assignments.values("user_id")).order_by("name", "id")


def singleton_id(items):
    return items[0]["id"] if len(items) == 1 else None


def assignment_options(actor, origin_id, destination_id=None):
    origin = Location.objects.filter(pk=origin_id, active=True, kind="CENTRO").first()
    if not is_admin(actor):
        require_role(actor, "PRODUCCION", origin_id)
    if origin is None:
        raise DomainError("VALIDATION_ERROR", "Origen no disponible.", 422)
    now = timezone.now()
    destinations = list(
        Location.objects.filter(
            active=True,
            kind="PUNTO_VENTA",
            pk__in=RoleAssignment.objects.filter(
                role_id="RECEPCION",
                scope="UBICACION",
                user__is_active=True,
                starts_at__lte=now,
            )
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
            .values("location_id"),
        )
        .order_by("code", "id")
        .values("id", "name")
    )
    if destination_id and destination_id not in {item["id"] for item in destinations}:
        raise DomainError("VALIDATION_ERROR", "Destino sin receptor vigente o no habilitado.", 422)
    selected = destination_id or singleton_id(destinations)
    drivers = list(assignable_users("TRANSPORTE", origin_id).values("id", "name"))
    receivers = (
        list(assignable_users("RECEPCION", selected).values("id", "name")) if selected else []
    )
    return {
        "drivers": drivers,
        "destinations": destinations,
        "receivers": receivers,
        "defaults": {
            "driver_id": singleton_id(drivers),
            "destination_id": selected,
            "receiver_id": singleton_id(receivers),
        },
    }


class OptionsQuery(StrictSerializer):
    origin_id = serializers.UUIDField()
    destination_id = serializers.UUIDField(required=False)


class MinimalOption(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()


class OptionDefaults(serializers.Serializer):
    driver_id = serializers.UUIDField(allow_null=True)
    destination_id = serializers.UUIDField(allow_null=True)
    receiver_id = serializers.UUIDField(allow_null=True)


class OptionsResponse(serializers.Serializer):
    drivers = MinimalOption(many=True)
    destinations = MinimalOption(many=True)
    receivers = MinimalOption(many=True)
    defaults = OptionDefaults()


class AssignmentOptionsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("origin_id", type={"type": "string", "format": "uuid"}, required=True),
            OpenApiParameter("destination_id", type={"type": "string", "format": "uuid"}),
        ],
        responses={
            200: OptionsResponse,
            401: ErrorSerializer,
            403: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def get(self, request):
        serializer = OptionsQuery(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return Response(
            OptionsResponse(assignment_options(request.user, **serializer.validated_data)).data
        )
