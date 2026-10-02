from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("traceability", "0005_correction")]
    operations = [
        migrations.RunSQL(
            """
CREATE FUNCTION sitrap_correction_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'correction history is immutable' USING ERRCODE='23000';
  END IF;
  IF (to_jsonb(NEW) - 'state' - 'lock_version' - 'finished_at') IS DISTINCT FROM
     (to_jsonb(OLD) - 'state' - 'lock_version' - 'finished_at') OR
     (OLD.state <> 'PENDIENTE' AND to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD))
  THEN RAISE EXCEPTION 'correction proposal and approvers are fixed' USING ERRCODE='23000'; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER correction_fixed BEFORE UPDATE OR DELETE ON traceability_correction
FOR EACH ROW EXECUTE FUNCTION sitrap_correction_fixed();
""",
            reverse_sql="""DROP TRIGGER correction_fixed ON traceability_correction; DROP FUNCTION sitrap_correction_fixed();""",
        )
    ]
