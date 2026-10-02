from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ErrorSerializer
from apps.sync.commands import dispatch
from apps.sync.serializers import OperationResultSerializer
from apps.traceability.commands import TransferCreateCommand, TransferUpdateCommand
from apps.traceability.lifecycle import TransferSendCommand
from apps.traceability.reads import lot_data, scoped_lots, scoped_transfers, timeline, transfer_data
from apps.traceability.serializers import LotSerializer, TimelineSerializer, TransferSerializer


class TransferReceipt(OperationResultSerializer):
    result = TransferSerializer()


def command_responses():
    error = PolymorphicProxySerializer(
        component_name="TransferCommandError",
        serializers=[OperationResultSerializer, ErrorSerializer],
        resource_type_field_name=None,
    )
    return {
        200: TransferReceipt,
        202: OperationResultSerializer,
        401: ErrorSerializer,
        403: ErrorSerializer,
        404: ErrorSerializer,
        409: error,
        422: error,
    }


class LotsView(generics.ListAPIView):
    serializer_class = LotSerializer

    def get_queryset(self):
        return scoped_lots(self.request.user).order_by("-created_at", "id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(
            LotSerializer([lot_data(item) for item in page], many=True).data
        )


class LotDetailView(generics.RetrieveAPIView):
    serializer_class = LotSerializer

    def get_queryset(self):
        return scoped_lots(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return Response(LotSerializer(lot_data(self.get_object())).data)


class TransfersView(generics.ListAPIView):
    @extend_schema(request=TransferCreateCommand, responses=command_responses())
    def post(self, request):
        body, status = dispatch(request.user, request.data, fixed_type="TRANSFER_CREATE")
        return Response(body, status=status)

    serializer_class = TransferSerializer

    def get_queryset(self):
        return scoped_transfers(self.request.user).order_by("code", "id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(
            TransferSerializer([transfer_data(item, request.user) for item in page], many=True).data
        )


class TransferDetailView(generics.RetrieveAPIView):
    @extend_schema(request=TransferUpdateCommand, responses=command_responses())
    def patch(self, request, pk):
        body, status = dispatch(
            request.user, request.data, fixed_type="TRANSFER_UPDATE", entity_id=pk
        )
        return Response(body, status=status)

    serializer_class = TransferSerializer

    def get_queryset(self):
        return scoped_transfers(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return Response(TransferSerializer(transfer_data(self.get_object(), request.user)).data)


class TimelineView(TransferDetailView):
    http_method_names = ["get", "head", "options"]

    @extend_schema(responses=TimelineSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return Response(TimelineSerializer(timeline(self.get_object()), many=True).data)


class SendTransferView(APIView):
    @extend_schema(request=TransferSendCommand, responses=command_responses())
    def post(self, request, pk):
        body, status = dispatch(
            request.user, request.data, fixed_type="TRANSFER_SEND", entity_id=pk
        )
        return Response(body, status=status)
