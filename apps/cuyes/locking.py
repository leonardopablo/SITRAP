import hashlib

from django.db import connection


def lock_centers(center_ids):
    """Shared by stock and commerce. Never take an order lock before this lock."""
    for center_id in sorted(set(map(str, center_ids))):
        key = int.from_bytes(hashlib.sha256(f"cuyes-stock:{center_id}".encode()).digest()[:8], "big", signed=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])
