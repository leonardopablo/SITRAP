from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ErrorSerializer
from apps.common.pagination import BoundedPagination
from apps.sync.services import owned_device

from .models import PushSubscription
from .push_config import public_config
from .subscriptions import SubscriptionInput, SubscriptionSerializer, subscribe, unsubscribe

DEVICE_HEADER = OpenApiParameter(
    "X-Device-ID",
    type={"type": "string", "format": "uuid"},
    location=OpenApiParameter.HEADER,
    required=True,
)


class PushConfigSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    vapid_public_key = serializers.CharField(allow_null=True)


class SubscriptionsPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = SubscriptionSerializer(many=True)


class PushConfigView(APIView):
    @extend_schema(responses=PushConfigSerializer)
    def get(self, request):
        return Response(public_config())


class PushSubscriptionsView(APIView):
    @extend_schema(parameters=[DEVICE_HEADER], responses=SubscriptionsPageSerializer)
    def get(self, request):
        id = serializers.UUIDField().run_validation(request.headers.get("X-Device-ID"))
        device = owned_device(request.user, id)
        rows = PushSubscription.objects.filter(user=request.user, device=device).order_by(
            "-created_at"
        )
        paginator = BoundedPagination()
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response(SubscriptionSerializer(page, many=True).data)

    @extend_schema(
        request=SubscriptionInput,
        responses={
            200: SubscriptionSerializer,
            403: ErrorSerializer,
            409: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = SubscriptionInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = subscribe(request.user, serializer.validated_data)
        request.session["device_id"] = str(subscription.device_id)
        return Response(SubscriptionSerializer(subscription).data)


class PushSubscriptionDetailView(APIView):
    @extend_schema(parameters=[DEVICE_HEADER], responses={204: None, 404: ErrorSerializer})
    def delete(self, request, pk):
        device_id = serializers.UUIDField().run_validation(request.headers.get("X-Device-ID"))
        unsubscribe(request.user, device_id, pk)
        return Response(status=204)
