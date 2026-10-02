from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import BoundedPagination
from apps.common.serializers import StrictSerializer

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "source_event_id",
            "entity_type",
            "entity_id",
            "version_id",
            "title",
            "text",
            "created_at",
            "read_at",
        ]


class NotificationPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    unread_count = serializers.IntegerField()
    results = NotificationSerializer(many=True)


class EmptyReadSerializer(StrictSerializer):
    pass


class NotificationsView(APIView):
    @extend_schema(responses=NotificationPageSerializer)
    def get(self, request):
        queryset = Notification.objects.filter(recipient=request.user).order_by(
            "-created_at", "-id"
        )
        paginator = BoundedPagination()
        rows = paginator.paginate_queryset(queryset, request)
        response = paginator.get_paginated_response(NotificationSerializer(rows, many=True).data)
        response.data["unread_count"] = queryset.filter(read_at__isnull=True).count()
        return response


class ReadNotificationView(APIView):
    @extend_schema(request=EmptyReadSerializer, responses=NotificationSerializer)
    @transaction.atomic
    def post(self, request, pk):
        serializer = EmptyReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification = get_object_or_404(
            Notification.objects.select_for_update(), pk=pk, recipient=request.user
        )
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)
