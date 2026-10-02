from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response

from apps.traceability.reads import lot_data, scoped_lots, scoped_transfers, timeline, transfer_data
from apps.traceability.serializers import LotSerializer, TimelineSerializer, TransferSerializer


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
    serializer_class = TransferSerializer

    def get_queryset(self):
        return scoped_transfers(self.request.user).order_by("code", "id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(
            TransferSerializer([transfer_data(item, request.user) for item in page], many=True).data
        )


class TransferDetailView(generics.RetrieveAPIView):
    serializer_class = TransferSerializer

    def get_queryset(self):
        return scoped_transfers(self.request.user)

    def retrieve(self, request, *args, **kwargs):
        return Response(TransferSerializer(transfer_data(self.get_object(), request.user)).data)


class TimelineView(TransferDetailView):
    @extend_schema(responses=TimelineSerializer(many=True))
    def get(self, request, *args, **kwargs):
        return Response(TimelineSerializer(timeline(self.get_object()), many=True).data)
