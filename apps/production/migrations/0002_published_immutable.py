from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("production", "0001_initial"), ("milk", "0002_initial")]
    operations = [
        migrations.RunSQL(
            sql="""
            CREATE FUNCTION sitrap_production_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.state <> 'BORRADOR' THEN
                    IF TG_OP = 'DELETE' THEN
                        RAISE EXCEPTION 'published version is immutable' USING ERRCODE='23000';
                    END IF;
                    IF (to_jsonb(NEW) - 'state') IS DISTINCT FROM (to_jsonb(OLD) - 'state')
                       OR NEW.state NOT IN ('PUBLICADA', 'SUPERADA')
                       OR (OLD.state = 'SUPERADA' AND NEW.state <> 'SUPERADA') THEN
                        RAISE EXCEPTION 'published version is immutable' USING ERRCODE='23000';
                    END IF;
                END IF;
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END; $$;
            CREATE TRIGGER production_version_immutable BEFORE UPDATE OR DELETE ON production_productionversion
            FOR EACH ROW EXECUTE FUNCTION sitrap_production_version_immutable();

            CREATE FUNCTION sitrap_milking_detail_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP <> 'INSERT' AND EXISTS(
                    SELECT 1 FROM production_productionversion WHERE id=OLD.version_id AND state <> 'BORRADOR'
                ) THEN
                    RAISE EXCEPTION 'published details are immutable' USING ERRCODE='23000';
                END IF;
                IF TG_OP <> 'DELETE' AND EXISTS(
                    SELECT 1 FROM production_productionversion WHERE id=NEW.version_id AND state <> 'BORRADOR'
                ) THEN
                    RAISE EXCEPTION 'published details are immutable' USING ERRCODE='23000';
                END IF;
                IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
                RETURN NEW;
            END; $$;
            CREATE TRIGGER milking_detail_immutable BEFORE INSERT OR UPDATE OR DELETE ON milk_milkingdetail
            FOR EACH ROW EXECUTE FUNCTION sitrap_milking_detail_immutable();
            """,
            reverse_sql="""
            DROP TRIGGER milking_detail_immutable ON milk_milkingdetail;
            DROP FUNCTION sitrap_milking_detail_immutable();
            DROP TRIGGER production_version_immutable ON production_productionversion;
            DROP FUNCTION sitrap_production_version_immutable();
            """,
        )
    ]
