import pytest
from django.db import connection, transaction


@pytest.mark.django_db(transaction=True)
def test_real_postgres_migrations_and_rollback():
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM django_migrations")
        assert cursor.fetchone()[0] > 0
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("CREATE TABLE sitrap_rollback_probe (id integer)")
            raise RuntimeError("rollback")
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('sitrap_rollback_probe')")
        assert cursor.fetchone()[0] is None
