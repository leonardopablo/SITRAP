"""Read-only, admin-scoped provenance for one milk lot."""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import require_admin
from apps.common.pagination import BoundedPagination

from .models import Lot, Transfer
from .serializers import LotTraceSerializer


def display_name(user):
    return user.name or user.username


def milestone(event):
    if event is None:
        return None
    return {
        "at": event.occurred_at,
        "registered_at": event.registered_at,
        "actor_name": display_name(event.user),
    }


def transfer_trace(transfer, lot):
    version = transfer.current_version
    line = next((row for row in version.lines.all() if row.lot_id == lot.id), None)
    events = list(transfer.trace_conformities)
    pickup = next((event for event in events if event.stage == "RECOGIDA"), None)
    reception = next((event for event in events if event.stage == "RECEPCION"), None)
    duration = None
    inconsistent_time = False
    if pickup and reception:
        seconds = (reception.occurred_at - pickup.occurred_at).total_seconds()
        inconsistent_time = seconds < 0
        if not inconsistent_time:
            duration = int(seconds // 60)
    return {
        "id": transfer.id,
        "code": transfer.code,
        "state": transfer.state,
        "quantity": line.quantity if line else None,
        "origin_name": version.origin.name,
        "destination_name": version.destination.name,
        "driver_name": display_name(version.driver),
        "receiver_name": display_name(version.receiver),
        "request_at": next(
            (item.published_at for item in transfer.trace_versions if item.published_at), None
        ),
        "pickup": milestone(pickup),
        "reception": milestone(reception),
        "travel_minutes": duration,
        "inconsistent_time": inconsistent_time,
        "has_history": transfer.version_count > 1 or bool(transfer.trace_corrections),
    }


class LotTraceView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("limit", int, description="Entregas por página (máximo 200)."),
            OpenApiParameter("offset", int, description="Desplazamiento de entregas."),
        ],
        responses=LotTraceSerializer,
    )
    def get(self, request, pk):
        require_admin(request.user)
        lot = get_object_or_404(
            Lot.objects.select_related(
                "production__current_version",
                "production__responsible",
                "production__center",
                "production__milking__turn",
            ),
            pk=pk,
        )
        production = lot.production
        linked_transfers = Transfer.objects.filter(versions__lines__lot=lot).distinct()
        draft_count = linked_transfers.filter(state="BORRADOR").count()
        transfers = (
            linked_transfers.exclude(state="BORRADOR")
            .distinct()
            .select_related(
                "current_version__origin",
                "current_version__destination",
                "current_version__driver",
                "current_version__receiver",
            )
            .prefetch_related("current_version__lines")
            .prefetch_related("versions__conformities__user", "corrections")
            .annotate(version_count=Count("versions", distinct=True))
            .order_by("code", "id")
        )
        paginator = BoundedPagination()
        page = paginator.paginate_queryset(transfers, request, view=self)
        # The nested physical confirmations may belong to an older document version.
        for transfer in page:
            transfer.trace_versions = sorted(transfer.versions.all(), key=lambda item: item.number)
            transfer.trace_conformities = sorted(
                (event for version in transfer.trace_versions for event in version.conformities.all()),
                key=lambda event: (event.occurred_at, str(event.id)),
            )
            transfer.trace_corrections = list(transfer.corrections.all())
        offset = paginator.get_offset(request)
        next_offset = offset + len(page) if offset + len(page) < paginator.count else None
        data = {
            "lot": {
                "id": lot.id,
                "code": lot.code,
                "production_id": production.id,
                "state": production.state,
                "date": production.milking.date,
                "confirmed_at": production.versions.filter(published_at__isnull=False)
                .order_by("number")
                .values_list("published_at", flat=True)
                .first(),
                "center_name": production.center.name,
                "turn_name": production.milking.turn.name,
                "responsible_name": display_name(production.responsible),
                "quantity": production.current_version.quantity,
            },
            "transfers": [transfer_trace(transfer, lot) for transfer in page],
            "count": paginator.count,
            "draft_count": draft_count,
            "next_offset": next_offset,
        }
        return Response(LotTraceSerializer(data).data)
