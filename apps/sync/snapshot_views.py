from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import ErrorSerializer
from apps.common.serializers import StrictSerializer

from .snapshots import page


class SnapshotQuery(StrictSerializer):
    cursor = serializers.CharField(required=False, max_length=2000)
    page = serializers.CharField(required=False, max_length=2000)
    limit = serializers.IntegerField(default=100, min_value=1, max_value=200)


class SnapshotHeader(StrictSerializer):
    device_id = serializers.UUIDField()


class SyncEntrySerializer(serializers.Serializer):
    entity_type = serializers.CharField()
    id = serializers.CharField()
    deleted = serializers.BooleanField()
    data = serializers.JSONField(allow_null=True)


class SnapshotResponse(serializers.Serializer):
    snapshot_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    preparation_expires_at = serializers.DateTimeField(allow_null=True)
    results = SyncEntrySerializer(many=True)
    next_page = serializers.CharField(allow_null=True)
    cursor = serializers.CharField(allow_null=True)


class BootstrapView(APIView):
    changes = False

    @extend_schema(
        parameters=[
            SnapshotQuery,
            OpenApiParameter("X-Device-ID", str, OpenApiParameter.HEADER, required=True),
        ],
        responses={
            200: SnapshotResponse,
            401: ErrorSerializer,
            403: ErrorSerializer,
            409: ErrorSerializer,
            410: ErrorSerializer,
            422: ErrorSerializer,
        },
    )
    def get(self, request):
        query = SnapshotQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        header = SnapshotHeader(data={"device_id": request.headers.get("X-Device-ID")})
        header.is_valid(raise_exception=True)
        return Response(
            SnapshotResponse(
                page(
                    request.user,
                    header.validated_data["device_id"],
                    query.validated_data,
                    changes=self.changes,
                )
            ).data
        )


class ChangesView(BootstrapView):
    changes = True
