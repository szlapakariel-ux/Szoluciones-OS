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
        null=True,
        blank=True,
        related_name="items_venta",
        verbose_name="Producto",
        help_text="Vacío si el ítem es un Combo (se completa 'Combo' en su lugar).",
    )
    combo = models.ForeignKey(
        "Combo",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="items_venta",
        verbose_name="Combo",
        help_text="Completar en vez de 'Producto' cuando el ítem es un combo de varios productos.",
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
    porciones = models.PositiveSmallIntegerField(
        "Porciones",
        null=True,
        blank=True,
        help_text=(
            "Si se vende una fracción puntual del producto (ej: 'media torta' pedida "
            "por el cliente) en vez de una unidad/presentación completa. No combinar "
            "con 'Combo'."
        ),
    )
    precio_unitario = models.DecimalField(
        "Precio unitario", max_digits=12, decimal_places=2
    )

    class Meta:
        verbose_name = "Ítem de venta"
        verbose_name_plural = "Ítems de venta"
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(producto__isnull=False, combo__isnull=True)
                    | models.Q(producto__isnull=True, combo__isnull=False)
                ),
                name="itemventa_producto_xor_combo",
            )
        ]

    def __str__(self):
        if self.combo_id:
            return f"{self.combo} × {self.cantidad}"
        return f"{self.producto} × {self.cantidad}"

    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.precio_unitario

    def clean(self):
        if bool(self.producto_id) == bool(self.combo_id):
            raise ValidationError(
                "Un ítem de venta debe tener exactamente uno de 'Producto' o 'Combo'."
            )
        if self.combo_id and self.porciones:
            raise ValidationError(
                {"porciones": "No se puede combinar 'Porciones' con 'Combo'."}
            )
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
        if self.porciones and self.producto_id:
            if self.producto.porciones_por_unidad <= 1:
                raise ValidationError(
                    {"porciones": "Este producto no está configurado para venderse fraccionado."}
                )
            if self.porciones > self.producto.porciones_por_unidad:
                raise ValidationError(
                    {"porciones": "No puede superar las porciones totales del producto."}
                )

    def save(self, *args, **kwargs):
        if not self.pk and (self.precio_unitario is None or self.precio_unitario == 0):
            if self.combo_id:
                self.precio_unitario = self.combo.precio
            elif self.presentacion_id:
                self.precio_unitario = self.presentacion.precio
            elif self.porciones:
                self.precio_unitario = (
                    self.producto.precio_venta
                    * self.porciones
                    / self.producto.porciones_por_unidad
                )
            else:
                self.precio_unitario = self.producto.precio_venta
        super().save(*args, **kwargs)


class Combo(TenantOwnedModel):
    nombre = models.CharField("Nombre", max_length=120)
    precio = models.DecimalField(
        "Precio del combo",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Combo"
        verbose_name_plural = "Combos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["negocio", "nombre"],
                name="combo_nombre_unico_por_negocio",
            )
        ]

    def __str__(self):
        return self.nombre


class ComboItem(TenantOwnedModel):
    combo = models.ForeignKey(
        Combo,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Combo",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="items_combo",
        verbose_name="Producto",
    )
    cantidad = models.PositiveSmallIntegerField(
        "Unidades enteras",
        default=1,
        help_text="Cantidad de unidades enteras de este producto que incluye el combo.",
    )
    porciones = models.PositiveSmallIntegerField(
        "Porciones",
        null=True,
        blank=True,
        help_text=(
            "Completar en vez de 'Unidades enteras' si el combo incluye solo una "
            "fracción de este producto (ej: mitad = la mitad de sus porciones totales)."
        ),
    )

    class Meta:
        verbose_name = "Ítem de combo"
        verbose_name_plural = "Ítems de combo"

    def __str__(self):
        if self.porciones:
            return f"{self.porciones} porciones de {self.producto}"
        return f"{self.cantidad} × {self.producto}"

    def clean(self):
        if self.porciones and self.producto_id:
            if self.producto.porciones_por_unidad <= 1:
                raise ValidationError(
                    {"porciones": "Este producto no está configurado para venderse fraccionado."}
                )
            if self.porciones > self.producto.porciones_por_unidad:
                raise ValidationError(
                    {"porciones": "No puede superar las porciones totales del producto."}
                )
        if self.combo_id and self.negocio_id and self.combo.negocio_id != self.negocio_id:
            raise ValidationError(
                {"combo": "El combo pertenece a otro negocio."}
            )


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
