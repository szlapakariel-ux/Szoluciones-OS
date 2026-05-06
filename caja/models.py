from django.db import models
from django.utils import timezone

from core.models import TenantOwnedModel


class MovimientoCaja(TenantOwnedModel):
    class Tipo(models.TextChoices):
        INGRESO = "INGRESO", "Ingreso"
        EGRESO = "EGRESO", "Egreso"

    class MetodoPago(models.TextChoices):
        EFECTIVO = "EFECTIVO", "Efectivo"
        DEBITO = "DEBITO", "Débito"
        CREDITO = "CREDITO", "Crédito"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"
        MERCADO_PAGO = "MP", "Mercado Pago"
        OTRO = "OTRO", "Otro"

    fecha = models.DateTimeField("Fecha", default=timezone.now)
    tipo = models.CharField("Tipo", max_length=10, choices=Tipo.choices)
    monto = models.DecimalField("Monto", max_digits=12, decimal_places=2)
    concepto = models.CharField("Concepto", max_length=200)
    metodo_pago = models.CharField(
        "Método de pago",
        max_length=20,
        choices=MetodoPago.choices,
        default=MetodoPago.EFECTIVO,
    )
    venta_origen = models.ForeignKey(
        "ventas.Venta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_caja",
        verbose_name="Venta de origen",
    )
    compra_origen = models.ForeignKey(
        "compras.Compra",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_caja",
        verbose_name="Compra de origen",
    )
    gasto_origen = models.ForeignKey(
        "gastos.GastoFijo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_caja",
        verbose_name="Gasto fijo de origen",
    )

    class Meta:
        verbose_name = "Movimiento de caja"
        verbose_name_plural = "Movimientos de caja"
        ordering = ["-fecha"]

    def __str__(self):
        signo = "+" if self.tipo == self.Tipo.INGRESO else "−"
        return f"{signo}${self.monto} · {self.concepto}"
