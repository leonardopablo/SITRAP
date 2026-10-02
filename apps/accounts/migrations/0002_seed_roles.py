from django.db import migrations


def seed_roles(apps, schema_editor):
    role = apps.get_model("accounts", "Role")
    for code in ("PRODUCCION", "TRANSPORTE", "RECEPCION", "ADMIN"):
        role.objects.get_or_create(code=code)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed_roles, migrations.RunPython.noop)]
