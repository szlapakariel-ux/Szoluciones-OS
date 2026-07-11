from decimal import Decimal

from django.db import models
from django.utils import timezone

from core.models import TenantOwnedModel


class UnidadMedida(models.TextChoices):
    UNIDAD = "UN", "Unidad"
    KILO = "KG", "Kilogramo"
    GRAMO = "GR", "Gramo"
    LITRO = "LT", "Litro"
    METRO = "MT", "Metro"
    DOCENA = "DC", "Docena"
    CAJA = "CA", "Caja"


class TipoProducto(models.TextChoices):
    VENTA = "VENTA", "Producto de venta"
    INSUMO = "INSUMO", "Insumo"


_UNIDAD_CORTA = {
    "UN": "unidad",
    "KG": "kg",
    "GR": "gr",
    "LT": "litro",
    "MT": "m",
    "DC": "docena",
    "CA": "caja",
}


class Producto(TenantOwnedModel):
    nombre = models.CharField("Nombre", max_length=120)
    codigo = models.CharField("Código", max_length=40, blank=True)
    tipo = models.CharField(
        "Tipo",
        max_length=10,
        choices=TipoProducto.choices,
        null=True,
        blank=True,
        help_text='Vacío = sin clasificar. Asignalo en /app/stock/ para que aparezca en POS o en recetas.',
    )
    presentacion = models.CharField(
        "Presentación",
        max_length=80,
        blank=True,
        help_text='Ej: "200 ml", "250 g", "Docena", "Caja x 12". Se muestra en el POS debajo del nombre.',
    )
    unidad_medida = models.CharField(
        "Unidad de medida",
        max_length=2,
        choices=UnidadMedida.choices,
        default=UnidadMedida.UNIDAD,
    )
    stock_actual = models.DecimalField(
        "Stock actual", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    stock_minimo = models.DecimalField(
        "Stock mínimo", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    precio_venta = models.DecimalField(
        "Precio de venta", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    cantidad_minima_mayorista = models.PositiveSmallIntegerField(
        "Cantidad mínima por mayor",
        null=True,
        blank=True,
        help_text=(
            "A partir de esta cantidad en una misma línea de venta se cobra "
            '"Precio por mayor" en vez de "Precio de venta" (ej: 6 facturas o más a '
            "$700 c/u en vez de $800). Vacío = no aplica precio por mayor."
        ),
    )
    precio_mayorista = models.DecimalField(
        "Precio por mayor",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Precio unitario que se cobra cuando se alcanza la "Cantidad mínima por mayor".',
    )
    costo = models.DecimalField(
        "Costo", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    activo = models.BooleanField("Activo", default=True)
    porciones_por_unidad = models.PositiveSmallIntegerField(
        "Porciones por unidad",
        default=1,
        help_text=(
            "Cantidad de porciones en que se puede fraccionar una unidad entera "
            '(ej: 4 para una torta, 16 para un budín). Dejar en 1 si el producto '
            "no se vende fraccionado."
        ),
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["negocio", "codigo"],
                condition=~models.Q(codigo=""),
                name="producto_codigo_unico_por_negocio",
            )
        ]

    def __str__(self):
        return self.nombre

    @property
    def unidad_corta(self):
        return _UNIDAD_CORTA.get(self.unidad_medida, self.get_unidad_medida_display().lower())

    def precio_para_cantidad(self, cantidad):
        """Precio unitario de lista para vender `cantidad` de este producto,
        aplicando el precio por mayor si se alcanza la cantidad mínima."""
        if (
            self.cantidad_minima_mayorista
            and self.precio_mayorista is not None
            and cantidad >= self.cantidad_minima_mayorista
        ):
            return self.precio_mayorista
        return self.precio_venta


class MovimientoStock(TenantOwnedModel):
    class Tipo(models.TextChoices):
        INGRESO = "INGRESO", "Ingreso"
        EGRESO = "EGRESO", "Egreso"
        AJUSTE = "AJUSTE", "Ajuste"

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="movimientos",
        verbose_name="Producto",
    )
    tipo = models.CharField("Tipo", max_length=10, choices=Tipo.choices)
    cantidad = models.DecimalField("Cantidad", max_digits=12, decimal_places=2)
    motivo = models.CharField("Motivo", max_length=160, blank=True)
    fecha = models.DateTimeField("Fecha", default=timezone.now)

    # FK de origen — permite inlines en Venta, Compra y Producción
    venta_origen = models.ForeignKey(
        "ventas.Venta",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="movimientos_stock",
        verbose_name="Venta de origen",
    )
    compra_origen = models.ForeignKey(
        "compras.Compra",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="movimientos_stock",
        verbose_name="Compra de origen",
    )
    produccion_origen = models.ForeignKey(
        "produccion.ProduccionRealizada",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="movimientos_stock",
        verbose_name="Producción de origen",
    )

    class Meta:
        verbose_name = "Movimiento de stock"
        verbose_name_plural = "Movimientos de stock"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo} · {self.producto} · {self.cantidad}"

    def aplicar_a_stock(self):
        delta = self.cantidad if self.tipo == self.Tipo.INGRESO else -self.cantidad
        if self.tipo == self.Tipo.AJUSTE:
            Producto.objects.all_tenants().filter(pk=self.producto_id).update(
                stock_actual=self.cantidad
            )
            return
        Producto.objects.all_tenants().filter(pk=self.producto_id).update(
            stock_actual=models.F("stock_actual") + delta
        )


class EstadoUnidadFisica(models.TextChoices):
    CERRADA = "CERRADA", "Cerrada"
    ABIERTA = "ABIERTA", "Abierta"
    AGOTADA = "AGOTADA", "Agotada"


class UnidadFisica(TenantOwnedModel):
    """Rastrea cada unidad entera físicamente producida de un producto fraccionable
    (ej: cada torta horneada), para distinguir "cerrada" (disponible para vender
    entera) de "abierta" (ya se le vendieron porciones, quedan sueltas en el
    mostrador). Solo aplica a productos con `porciones_por_unidad` > 1."""

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="unidades_fisicas",
        verbose_name="Producto",
    )
    estado = models.CharField(
        "Estado", max_length=10, choices=EstadoUnidadFisica.choices,
        default=EstadoUnidadFisica.CERRADA,
    )
    porciones_restantes = models.PositiveSmallIntegerField("Porciones restantes", default=0)

    class Meta:
        verbose_name = "Unidad física"
        verbose_name_plural = "Unidades físicas"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.producto} · {self.get_estado_display()} ({self.porciones_restantes} porc.)"
