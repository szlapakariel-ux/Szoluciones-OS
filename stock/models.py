from decimal import Decimal

from django.db import models

from core.models import TenantOwnedModel


class UnidadMedida(models.TextChoices):
    UNIDAD = "UN", "Unidad"
    KILO = "KG", "Kilogramo"
    GRAMO = "GR", "Gramo"
    LITRO = "LT", "Litro"
    METRO = "MT", "Metro"
    DOCENA = "DC", "Docena"
    CAJA = "CA", "Caja"


class Producto(TenantOwnedModel):
    nombre = models.CharField("Nombre", max_length=120)
    codigo = models.CharField("Código", max_length=40, blank=True)
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
    costo = models.DecimalField(
        "Costo", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    activo = models.BooleanField("Activo", default=True)

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
    fecha = models.DateTimeField("Fecha", auto_now_add=True)

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
