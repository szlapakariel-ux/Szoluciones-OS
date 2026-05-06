from django.db import models

from core.models import TenantOwnedModel


class GastoFijo(TenantOwnedModel):
    class Periodicidad(models.TextChoices):
        DIARIA = "DIARIA", "Diaria"
        SEMANAL = "SEMANAL", "Semanal"
        MENSUAL = "MENSUAL", "Mensual"
        ANUAL = "ANUAL", "Anual"

    concepto = models.CharField("Concepto", max_length=120)
    monto = models.DecimalField("Monto", max_digits=12, decimal_places=2)
    periodicidad = models.CharField(
        "Periodicidad",
        max_length=10,
        choices=Periodicidad.choices,
        default=Periodicidad.MENSUAL,
    )
    proximo_vencimiento = models.DateField(
        "Próximo vencimiento", null=True, blank=True
    )
    activo = models.BooleanField("Activo", default=True)
    notas = models.TextField("Notas", blank=True)

    class Meta:
        verbose_name = "Gasto fijo"
        verbose_name_plural = "Gastos fijos"
        ordering = ["proximo_vencimiento", "concepto"]

    def __str__(self):
        return f"{self.concepto} (${self.monto} / {self.get_periodicidad_display()})"
