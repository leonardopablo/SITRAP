from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [
        migrations.RunSQL(
            sql="""
                CREATE FUNCTION sitrap_audit_append_only() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN
                    RAISE EXCEPTION 'audit entries are append-only'
                    USING ERRCODE = '23000';
                END;
                $$;
                CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE
                ON audit_auditentry FOR EACH ROW EXECUTE FUNCTION sitrap_audit_append_only();
            """,
            reverse_sql="""
                DROP TRIGGER audit_append_only ON audit_auditentry;
                DROP FUNCTION sitrap_audit_append_only();
            """,
        ),
    ]
