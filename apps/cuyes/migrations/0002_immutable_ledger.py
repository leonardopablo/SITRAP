from django.db import migrations

TABLES = ["cuyes_movement", "cuyes_ledgerline", "cuyes_countdetail", "cuyes_dailyrevision", "cuyes_cuylot"]


class Migration(migrations.Migration):
    dependencies = [("cuyes", "0001_initial"), ("accounts", "0005_seed_galponero")]
    operations = [
        migrations.RunSQL(
            """
            CREATE FUNCTION cuy_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Cuyes history is append-only' USING ERRCODE = '23514'; END;
            $$;
            """ + "\n".join(
                f"CREATE TRIGGER immutable_cuy_history BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION cuy_append_only();" for table in TABLES
            ),
            "\n".join(f"DROP TRIGGER immutable_cuy_history ON {table};" for table in TABLES)
            + "\nDROP FUNCTION cuy_append_only();",
        ),
    ]
