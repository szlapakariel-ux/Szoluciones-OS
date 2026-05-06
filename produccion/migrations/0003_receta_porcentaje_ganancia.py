from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("produccion", "0002_alter_receta_rendimiento_produccionrealizada"),
    ]

    operations = [
        migrations.AddField(
            model_name="receta",
            name="porcentaje_ganancia",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("30"),
                help_text="Porcentaje de ganancia sobre el costo unitario para calcular el precio sugerido.",
                max_digits=5,
                verbose_name="% Ganancia objetivo",
            ),
        ),
    ]
