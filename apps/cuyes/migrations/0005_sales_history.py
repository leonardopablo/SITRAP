from django.db import migrations

TABLES = [
    "cuyes_salepayment", "cuyes_salefinancialreview", "cuyes_saledispatch",
    "cuyes_saledispatchdetail", "cuyes_saledelivery", "cuyes_saleconformity",
    "cuyes_salepreparation", "cuyes_dispatchselection", "cuyes_salerevision",
    "cuyes_reservationdetail", "cuyes_paymentevidence",
]


class Migration(migrations.Migration):
    dependencies = [
        ("cuyes", "0004_breedingmodule_paymentevidence_saledispatch_saleline_and_more"),
    ]
    operations = [
        migrations.RunSQL(
            "\n".join(
                f"CREATE TRIGGER immutable_sale_history BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION cuy_append_only();" for table in TABLES
            ),
            "\n".join(f"DROP TRIGGER immutable_sale_history ON {table};" for table in TABLES),
        ),
    ]
