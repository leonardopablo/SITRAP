from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ErrorSerializer
from apps.sync.serializers import DeviceInputSerializer, DeviceSerializer
from apps.sync.services import owned_device, register_device


class DeviceView(APIView):
    @extend_schema(
        request=DeviceInputSerializer,
        responses={
            200: DeviceSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            409: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def post(self, request):
        serializer = DeviceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device = register_device(request.user, serializer.validated_data)
        request.session["device_id"] = str(device.id)
        return Response(DeviceSerializer(device).data)


class CurrentDeviceView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                "X-Device-ID",
                type={"type": "string", "format": "uuid"},
                location=OpenApiParameter.HEADER,
                required=True,
            )
        ],
        responses={
            200: DeviceSerializer,
            401: ErrorSerializer,
            403: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def get(self, request):
        device_id = serializers.UUIDField().run_validation(request.headers.get("X-Device-ID"))
        return Response(DeviceSerializer(owned_device(request.user, device_id)).data)
