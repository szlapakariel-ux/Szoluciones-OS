from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
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
    presentacion = models.ForeignKey(
        "PresentacionVenta",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="items_venta",
        verbose_name="Presentación de venta",
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

    def clean(self):
        if self.presentacion_id:
            pv = self.presentacion
            if self.producto_id and pv.producto_id != self.producto_id:
                raise ValidationError(
                    {"presentacion": "La presentación no pertenece al producto seleccionado."}
                )
            if self.negocio_id and pv.negocio_id != self.negocio_id:
                raise ValidationError(
                    {"presentacion": "La presentación pertenece a otro negocio."}
                )
            if not pv.activo and not self.pk:
                raise ValidationError(
                    {"presentacion": "No se puede usar una presentación inactiva en una nueva venta."}
                )

    def save(self, *args, **kwargs):
        if not self.pk and (self.precio_unitario is None or self.precio_unitario == 0):
            if self.presentacion_id:
                self.precio_unitario = self.presentacion.precio
            else:
                self.precio_unitario = self.producto.precio_venta
        super().save(*args, **kwargs)


class PresentacionVenta(TenantOwnedModel):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="presentaciones",
        verbose_name="Producto",
    )
    nombre = models.CharField("Nombre", max_length=80)
    factor = models.DecimalField(
        "Factor de stock",
        max_digits=12,
        decimal_places=2,
        help_text="Unidades de stock base que descuenta esta presentación.",
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    precio = models.DecimalField(
        "Precio de venta",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Presentación de venta"
        verbose_name_plural = "Presentaciones de venta"
        ordering = ["producto", "factor"]
        constraints = [
            models.UniqueConstraint(
                fields=["negocio", "producto", "nombre"],
                name="presentacion_nombre_unico_por_producto_negocio",
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.producto})"

    def save(self, *args, **kwargs):
        if not self.negocio_id and self.producto_id:
            self.negocio_id = self.producto.negocio_id
        super().save(*args, **kwargs)

    def clean(self):
        if self.producto_id and self.negocio_id:
            if self.producto.negocio_id != self.negocio_id:
                raise ValidationError(
                    {"producto": "El producto debe pertenecer al mismo negocio que la presentación."}
                )
