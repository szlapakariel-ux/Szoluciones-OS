from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0003_producto_presentacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="producto",
            name="tipo",
            field=models.CharField(
                blank=True,
                choices=[("VENTA", "Producto de venta"), ("INSUMO", "Insumo")],
                help_text="Vacío = sin clasificar. Asignalo en /app/stock/ para que aparezca en POS o en recetas.",
                max_length=10,
                null=True,
                verbose_name="Tipo",
            ),
        ),
    ]
