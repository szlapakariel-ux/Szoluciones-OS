from decimal import Decimal

from django.db import models
from django.utils import timezone

from caja.models import MovimientoCaja
from clientes.models import Cliente
from core.models import TenantOwnedModel
from stock.models import Producto


class Venta(TenantOwnedModel):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventas",
        verbose_name="Cliente",
    )
    fecha = models.DateTimeField("Fecha", default=timezone.now)
    total = models.DecimalField(
        "Total", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    metodo_pago = models.CharField(
        "Método de pago",
        max_length=20,
        choices=MovimientoCaja.MetodoPago.choices,
        default=MovimientoCaja.MetodoPago.EFECTIVO,
    )
    observaciones = models.TextField("Observaciones", blank=True)

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-fecha"]

    def __str__(self):
        if self.cliente:
            return f"Venta #{self.pk} · {self.cliente} · {self.fecha:%d/%m %H:%M}"
        return f"Venta #{self.pk} · {self.fecha:%d/%m %H:%M}"

    def recalcular_total(self):
        total = sum(
            (item.cantidad * item.precio_unitario for item in self.items.all()),
            Decimal("0"),
        )
        Venta.objects.all_tenants().filter(pk=self.pk).update(total=total)
        self.total = total


class ItemVenta(TenantOwnedModel):
    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Venta",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="items_venta",
        verbose_name="Producto",
    )
    cantidad = models.DecimalField("Cantidad", max_digits=12, decimal_places=2)
    precio_unitario = models.DecimalField(
        "Precio unitario", max_digits=12, decimal_places=2
    )

    class Meta:
        verbose_name = "Ítem de venta"
        verbose_name_plural = "Ítems de venta"

    def __str__(self):
        return f"{self.producto} × {self.cantidad}"

    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.precio_unitario

    def save(self, *args, **kwargs):
        if not self.pk and (self.precio_unitario is None or self.precio_unitario == 0):
            self.precio_unitario = self.producto.precio_venta
        super().save(*args, **kwargs)
