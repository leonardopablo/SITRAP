from urllib.parse import urlencode

from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import active_assignments, require_admin
from apps.catalog.models import Location
from apps.common.errors import DomainError, ErrorSerializer
from apps.sync.commands import dispatch
from apps.sync.serializers import OperationResultSerializer

from .access import enabled_centers
from .models import BreedingModule
from .sales_private import deliver_with_pin, download_evidence, generate_pin, upload_evidence
from .sales_reads import (
    availability_data,
    candidates,
    module_data,
    order_data,
    orders_for,
    workspace,
)
from .sales_serializers import (
    SALE_COMMANDS,
    ModuleInput,
    ObjectPage,
    PinDeliveryInput,
    PinGenerationInput,
    PinGenerationOutput,
    SaleOutput,
    SalePage,
    SalesOptionsOutput,
    SalesQuery,
    VoucherInput,
    VoucherOutput,
)
from .sales_services import save_module
from .services import fail, get

ERRORS = {401: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer, 409: ErrorSerializer, 422: ErrorSerializer, 429: ErrorSerializer}


def query(request):
    serializer = SalesQuery(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    p = serializer.validated_data
    return p, workspace(request.user, p.get("workspace"))


def paged(request, rows, p, serialize):
    count = rows.count() if hasattr(rows, "model") else len(rows)
    end = p["offset"] + p["limit"]
    next_params = request.query_params.dict()
    next_params["offset"] = end
    return Response({
        "count": count, "next": f"{request.path}?{urlencode(next_params)}" if end < count else None,
        "results": [serialize(row) for row in rows[p["offset"]:end]],
    })


class ModulesView(APIView):
    @extend_schema(parameters=[SalesQuery], responses={200: ObjectPage, **ERRORS})
    def get(self, request):
        p, role = query(request)
        if role == "TRANSPORTE":
            fail("Transporte no consulta el catálogo comercial.", "PERMISSION_DENIED", 403)
        rows = BreedingModule.objects.order_by("name", "id")
        if role != "ADMIN":
            rows = rows.filter(active=True)
        return paged(request, rows, p, module_data)

    @extend_schema(request=ModuleInput, responses={200: dict, **ERRORS})
    def post(self, request):
        serializer = ModuleInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(module_data(save_module(request.user, serializer.validated_data)))


class AvailabilityView(APIView):
    @extend_schema(parameters=[SalesQuery], responses={200: dict, **ERRORS})
    def get(self, request):
        p, role = query(request)
        if not p.get("center_id"):
            fail("Seleccione centro.", "VALIDATION_ERROR", 422)
        return Response(availability_data(request.user, p["center_id"], role))


class OrdersView(APIView):
    @extend_schema(parameters=[SalesQuery], responses={200: SalePage, **ERRORS})
    def get(self, request):
        p, role = query(request)
        rows = orders_for(request.user, role)
        if p.get("center_id"):
            rows = rows.filter(center_id=p["center_id"])
        if p.get("state"):
            rows = rows.filter(state=p["state"])
        return paged(request, rows.order_by("-created_at", "-id"), p, lambda o: order_data(request.user, o, role))


class OrderDetailView(APIView):
    @extend_schema(operation_id="cuyes_sale_order_detail", parameters=[SalesQuery], responses={200: SaleOutput, **ERRORS})
    def get(self, request, pk):
        p, role = query(request)
        return Response(order_data(request.user, get(orders_for(request.user, role), pk), role))


class CandidatesView(APIView):
    @extend_schema(parameters=[SalesQuery], responses={200: ObjectPage, **ERRORS})
    def get(self, request, pk):
        p, role = query(request)
        order = get(orders_for(request.user, role), pk)
        return paged(request, candidates(request.user, order), p, lambda row: row)


class CommercialCommandsView(APIView):
    @extend_schema(
        request=PolymorphicProxySerializer(component_name="SaleCommand", serializers=SALE_COMMANDS, resource_type_field_name="type"),
        responses={200: OperationResultSerializer, **ERRORS},
    )
    def post(self, request):
        if request.data.get("type") not in SALE_COMMANDS:
            fail("Comando comercial no válido.", "VALIDATION_ERROR", 422)
        body, status = dispatch(request.user, request.data)
        return Response(body, status=status)


@method_decorator(sensitive_post_parameters("pin"), name="dispatch")
class PinGenerateView(APIView):
    @extend_schema(request=PinGenerationInput, responses={200: PinGenerationOutput, **ERRORS})
    @sensitive_variables()
    def post(self, request, pk):
        serializer = PinGenerationInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = Response(generate_pin(request.user, pk, serializer.validated_data))
        response["Cache-Control"] = "no-store, private"
        return response


@method_decorator(sensitive_post_parameters("pin"), name="dispatch")
class PinDeliveryView(APIView):
    @extend_schema(request=PinDeliveryInput, responses={200: OperationResultSerializer, **ERRORS})
    @sensitive_variables()
    def post(self, request, pk):
        serializer = PinDeliveryInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        body, status = deliver_with_pin(request.user, pk, serializer.validated_data)
        if body.get("result", {}).get("pin_valid") is False:
            response = Response(DomainError("PIN_INVALID", "PIN incorrecto.", 422).detail, status=422)
        else:
            response = Response(body, status=status)
        response["Cache-Control"] = "no-store, private"
        return response


class VouchersView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=VoucherInput, responses={200: VoucherOutput, **ERRORS})
    def post(self, request):
        serializer = VoucherInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        evidence = upload_evidence(request.user, serializer.validated_data)
        return Response({"id": evidence.id, "size": evidence.size, "content_type": evidence.content_type})


class VoucherDetailView(APIView):
    @extend_schema(responses={(200, "application/octet-stream"): bytes, **ERRORS})
    def get(self, request, pk):
        return download_evidence(request.user, pk)


class SalesOptionsView(APIView):
    @extend_schema(responses={200: SalesOptionsOutput, **ERRORS})
    def get(self, request):
        require_admin(request.user)
        from apps.accounts.models import User

        return Response({
            "centers": list(Location.objects.filter(id__in=enabled_centers()).values("id", "name")),
            "points": list(Location.objects.filter(kind="PUNTO_VENTA", active=True).values("id", "name")),
            "drivers": [
                {"id": user.id, "name": user.name, "center_ids": list(active_assignments(user).filter(role_id="TRANSPORTE").values_list("location_id", flat=True))}
                for user in User.objects.filter(is_active=True)
                if active_assignments(user).filter(role_id="TRANSPORTE").exists()
            ],
        })
