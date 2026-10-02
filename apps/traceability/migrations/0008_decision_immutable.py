from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("traceability", "0007_correctiondecision")]
    operations = [
        migrations.RunSQL(
            """CREATE TRIGGER correction_decision_immutable BEFORE UPDATE OR DELETE ON traceability_correctiondecision
        FOR EACH ROW EXECUTE FUNCTION sitrap_conformity_immutable();""",
            reverse_sql="DROP TRIGGER correction_decision_immutable ON traceability_correctiondecision;",
        )
    ]
