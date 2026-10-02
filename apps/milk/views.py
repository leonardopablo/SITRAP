from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ErrorSerializer
from apps.milk.serializers import (
    MilkingConfirmCommand,
    MilkingCreateCommand,
    MilkingReceipt,
    MilkingSerializer,
    MilkingUpdateCommand,
)
from apps.milk.services import milking_data, scoped_milkings
from apps.sync.commands import dispatch
from apps.sync.serializers import OperationResultSerializer


def command_responses():
    error = PolymorphicProxySerializer(
        component_name="MilkingCommandError",
        serializers=[OperationResultSerializer, ErrorSerializer],
        resource_type_field_name=None,
    )
    return {
        200: MilkingReceipt,
        202: OperationResultSerializer,
        401: ErrorSerializer,
        403: ErrorSerializer,
        404: ErrorSerializer,
        409: error,
        422: error,
    }


class MilkingsView(generics.ListAPIView):
    serializer_class = MilkingSerializer

    def get_queryset(self):
        return scoped_milkings(self.request.user).order_by("-date", "id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([milking_data(item, request.user) for item in page])

    @extend_schema(request=MilkingCreateCommand, responses=command_responses())
    def post(self, request):
        body, status = dispatch(request.user, request.data, fixed_type="MILKING_CREATE")
        return Response(body, status=status)


class MilkingDetailView(generics.RetrieveAPIView):
    serializer_class = MilkingSerializer

    def get_queryset(self):
        return scoped_milkings(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return Response(milking_data(self.get_object(), request.user))

    @extend_schema(request=MilkingUpdateCommand, responses=command_responses())
    def patch(self, request, pk):
        body, status = dispatch(
            request.user, request.data, fixed_type="MILKING_UPDATE", entity_id=pk
        )
        return Response(body, status=status)


class MilkingConfirmView(APIView):
    @extend_schema(request=MilkingConfirmCommand, responses=command_responses())
    def post(self, request, pk):
        body, status = dispatch(
            request.user, request.data, fixed_type="MILKING_CONFIRM", entity_id=pk
        )
        return Response(body, status=status)
