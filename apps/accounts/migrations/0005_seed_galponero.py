from django.db import migrations


def seed(apps, schema_editor):
    apps.get_model("accounts", "Role").objects.get_or_create(code="GALPONERO")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_remove_role_role_known_code_alter_role_code_and_more")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
