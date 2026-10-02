from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("traceability", "0002_transfer_transferversion_transferline_and_more")]
    operations = [
        migrations.RunSQL(
            sql="""
CREATE FUNCTION sitrap_transfer_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state <> 'BORRADOR' THEN
    IF TG_OP = 'DELETE' THEN
      RAISE EXCEPTION 'document is immutable' USING ERRCODE='23000';
    END IF;
    IF (to_jsonb(NEW) - 'state' - 'published_at') IS DISTINCT FROM (to_jsonb(OLD) - 'state' - 'published_at')
      OR (OLD.state='PROPUESTA' AND NEW.state NOT IN ('PROPUESTA','PUBLICADA','RETIRADA'))
      OR (OLD.state='PUBLICADA' AND NEW.state NOT IN ('PUBLICADA','SUPERADA'))
      OR (OLD.state IN ('SUPERADA','RETIRADA') AND NEW.state <> OLD.state)
      OR (OLD.state <> 'PROPUESTA' AND NEW.published_at IS DISTINCT FROM OLD.published_at)
    THEN RAISE EXCEPTION 'document is immutable' USING ERRCODE='23000'; END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER transfer_version_immutable BEFORE UPDATE OR DELETE ON traceability_transferversion
FOR EACH ROW EXECUTE FUNCTION sitrap_transfer_version_immutable();

CREATE FUNCTION sitrap_transfer_line_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP <> 'INSERT' AND EXISTS(SELECT 1 FROM traceability_transferversion WHERE id=OLD.version_id AND state <> 'BORRADOR') THEN
    RAISE EXCEPTION 'document line is immutable' USING ERRCODE='23000';
  END IF;
  IF TG_OP <> 'DELETE' AND EXISTS(SELECT 1 FROM traceability_transferversion WHERE id=NEW.version_id AND state <> 'BORRADOR') THEN
    RAISE EXCEPTION 'document line is immutable' USING ERRCODE='23000';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END; $$;
CREATE TRIGGER transfer_line_immutable BEFORE INSERT OR UPDATE OR DELETE ON traceability_transferline
FOR EACH ROW EXECUTE FUNCTION sitrap_transfer_line_immutable();
""",
            reverse_sql="""DROP TRIGGER transfer_line_immutable ON traceability_transferline;
DROP FUNCTION sitrap_transfer_line_immutable();
DROP TRIGGER transfer_version_immutable ON traceability_transferversion;
DROP FUNCTION sitrap_transfer_version_immutable();""",
        )
    ]
