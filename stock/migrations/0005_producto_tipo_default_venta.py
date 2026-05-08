from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0004_producto_tipo"),
    ]

    operations = [
        migrations.RunSQL(
            sql="UPDATE stock_producto SET tipo = 'VENTA' WHERE tipo IS NULL OR tipo = '';",
            reverse_sql="UPDATE stock_producto SET tipo = NULL WHERE tipo = 'VENTA';",
        ),
    ]
