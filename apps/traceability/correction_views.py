from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sync.commands import dispatch
from apps.sync.serializers import OperationResultSerializer

from .correction_closing import CorrectionRejectCommand, CorrectionWithdrawCommand
from .corrections import (
    CorrectionCreateCommand,
    CorrectionCreatedSerializer,
    CorrectionSerializer,
    correction_data,
    scoped_corrections,
)
from .decisions import CorrectionAcceptCommand
from .views import command_responses


class CorrectionCreateReceipt(OperationResultSerializer):
    result = CorrectionCreatedSerializer()


class CreateCorrectionView(APIView):
    @extend_schema(
        request=CorrectionCreateCommand,
        responses={**command_responses(), 200: CorrectionCreateReceipt},
    )
    def post(self, request, pk):
        body, status = dispatch(
            request.user, request.data, fixed_type="CORRECTION_CREATE", entity_id=pk
        )
        return Response(body, status=status)


class CorrectionsView(generics.ListAPIView):
    serializer_class = CorrectionSerializer

    def get_queryset(self):
        return scoped_corrections(self.request.user).order_by("-created_at", "-id")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(
            CorrectionSerializer([correction_data(c, request.user) for c in page], many=True).data
        )


class CorrectionDetailView(APIView):
    @extend_schema(responses=CorrectionSerializer)
    def get(self, request, pk):
        correction = get_object_or_404(scoped_corrections(request.user), pk=pk)
        return Response(CorrectionSerializer(correction_data(correction, request.user)).data)


class CorrectionDecisionReceipt(OperationResultSerializer):
    result = CorrectionSerializer()


class AcceptCorrectionView(APIView):
    @extend_schema(
        request=CorrectionAcceptCommand,
        responses={**command_responses(), 200: CorrectionDecisionReceipt},
    )
    def post(self, request, pk):
        body, status = dispatch(
            request.user, request.data, fixed_type="CORRECTION_ACCEPT", entity_id=pk
        )
        return Response(body, status=status)


class RejectCorrectionView(APIView):
    @extend_schema(
        request=CorrectionRejectCommand,
        responses={**command_responses(), 200: CorrectionDecisionReceipt},
    )
    def post(self, request, pk):
        body, status = dispatch(
            request.user, request.data, fixed_type="CORRECTION_REJECT", entity_id=pk
        )
        return Response(body, status=status)


class WithdrawCorrectionView(APIView):
    @extend_schema(
        request=CorrectionWithdrawCommand,
        responses={**command_responses(), 200: CorrectionDecisionReceipt},
    )
    def post(self, request, pk):
        body, status = dispatch(
            request.user, request.data, fixed_type="CORRECTION_WITHDRAW", entity_id=pk
        )
        return Response(body, status=status)
