from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("traceability", "0003_document_immutability")]
    operations = [
        migrations.RunSQL(
            """
CREATE FUNCTION sitrap_conformity_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'conformities are immutable' USING ERRCODE='23000'; END; $$;
CREATE TRIGGER conformity_immutable BEFORE UPDATE OR DELETE ON traceability_conformity
FOR EACH ROW EXECUTE FUNCTION sitrap_conformity_immutable();
CREATE TRIGGER conformity_detail_immutable BEFORE UPDATE OR DELETE ON traceability_conformitydetail
FOR EACH ROW EXECUTE FUNCTION sitrap_conformity_immutable();
""",
            reverse_sql="""DROP TRIGGER conformity_detail_immutable ON traceability_conformitydetail;
DROP TRIGGER conformity_immutable ON traceability_conformity;
DROP FUNCTION sitrap_conformity_immutable();""",
        )
    ]
