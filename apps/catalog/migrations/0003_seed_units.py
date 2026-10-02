from django.db import migrations


def seed(apps, schema_editor):
    unit = apps.get_model("catalog", "Unit")
    for code, name in (("L", "Litro"), ("KG", "Kilogramo"), ("UN", "Unidad")):
        unit.objects.get_or_create(code=code, defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_unit_product_centerproduct")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
