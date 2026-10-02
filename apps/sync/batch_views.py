from django.conf import settings
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import DomainError, ErrorSerializer

from .batch import OFFLINE_TYPES, process, validate_batch
from .commands import registry
from .serializers import OperationResultSerializer


class BatchOperationResult(OperationResultSerializer):
    status = serializers.ChoiceField(
        choices=["APLICADA", "RECHAZADA", "ESPERA_DEPENDENCIA", "NO_PROCESADA"]
    )
    persisted = serializers.BooleanField()
    http_status = serializers.IntegerField()


class BatchResponse(serializers.Serializer):
    results = BatchOperationResult(many=True)
    reprocessed = BatchOperationResult(many=True)


class SyncEventsView(APIView):
    @extend_schema(
        request=inline_serializer(
            name="OfflineBatchInput",
            fields={
                "events": PolymorphicProxySerializer(
                    component_name="OfflineCommand",
                    serializers={name: registry()[name][0] for name in sorted(OFFLINE_TYPES)},
                    resource_type_field_name="type",
                    many=True,
                )
            },
        ),
        responses={
            200: BatchResponse,
            401: ErrorSerializer,
            403: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def post(self, request):
        if len(request.body) > settings.SYNC_MAX_BATCH_BYTES:
            raise DomainError("VALIDATION_ERROR", "Lote demasiado grande.", 422)
        events = validate_batch(request.data)
        return Response(process(request.user, events))
