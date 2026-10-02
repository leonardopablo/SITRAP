from functools import wraps

from django.db import connection, transaction
from rest_framework import serializers

from apps.common.errors import DomainError
from apps.common.serializers import StrictSerializer


class PeriodQuery(StrictSerializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    center_id = serializers.UUIDField(required=False)
    product_id = serializers.UUIDField(required=False)

    def validate(self, data):
        days = (data["date_to"] - data["date_from"]).days + 1
        if not 1 <= days <= 366:
            raise serializers.ValidationError("Seleccione entre 1 y 366 dÃ­as.")
        return data


def snapshot(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            return function(*args, **kwargs)

    return wrapped


def bounded(queryset, limit=10000):
    rows = list(queryset[: limit + 1])
    if len(rows) > limit:
        raise DomainError("REPORT_TOO_LARGE", "Reduzca el perÃ­odo o los filtros.", 422)
    return rows


def metadata(filters):
    with connection.cursor() as cursor:
        cursor.execute("SELECT transaction_timestamp()")
        cutoff = cursor.fetchone()[0]
    return {
        "date_from": filters["date_from"],
        "date_to": filters["date_to"],
        "cutoff": cutoff,
        "timezone": "America/Lima",
        "synchronized_only": True,
    }


def decimal(value):
    return format(value, ".3f") if value is not None else None
