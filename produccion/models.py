from decimal import Decimal

from django.db import models
from django.utils import timezone

from core.models import TenantOwnedModel
from stock.models import Producto


class Receta(TenantOwnedModel):
    nombre = models.CharField("Nombre de la receta", max_length=120)
    producto_resultante = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="recetas",
        verbose_name="Producto resultante",
    )
    rendimiento = models.DecimalField(
        "Rendimiento",
        max_digits=12,
        decimal_places=2,
        default=Decimal("1"),
        help_text="Cantidad de producto resultante que produce esta receta (un lote).",
    )
    porcentaje_ganancia = models.DecimalField(
        "% Ganancia objetivo",
        max_digits=5,
        decimal_places=2,
        default=Decimal("30"),
        help_text="Porcentaje de ganancia sobre el costo unitario para calcular el precio sugerido.",
    )
    instrucciones = models.TextField("Instrucciones", blank=True)

    class Meta:
        verbose_name = "Receta"
        verbose_name_plural = "Recetas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def costo_total(self) -> Decimal:
        return sum(
            (i.costo_ingrediente for i in self.ingredientes.all()),
            Decimal("0"),
        )

    @property
    def costo_unitario(self) -> Decimal:
        if self.rendimiento and self.rendimiento > 0:
            return self.costo_total / self.rendimiento
        return Decimal("0")

    @property
    def precio_sugerido(self) -> Decimal:
        """Precio de venta sugerido = costo_unitario × (1 + ganancia%)."""
        return self.costo_unitario * (1 + self.porcentaje_ganancia / 100)

    @property
    def margen_real_pct(self) -> Decimal:
        """Margen bruto real usando el precio de venta actual del producto."""
        precio = self.producto_resultante.precio_venta
        if precio > 0:
            return (precio - self.costo_unitario) / precio * 100
        return Decimal("0")


class Ingrediente(TenantOwnedModel):
    receta = models.ForeignKey(
        Receta,
        on_delete=models.CASCADE,
        related_name="ingredientes",
        verbose_name="Receta",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="usado_en_recetas",
        verbose_name="Producto",
    )
    cantidad = models.DecimalField("Cantidad", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Ingrediente"
        verbose_name_plural = "Ingredientes"

    def __str__(self):
        return f"{self.cantidad} {self.producto.unidad_medida} — {self.producto}"

    @property
    def costo_ingrediente(self) -> Decimal:
        """Costo de usar esta cantidad del producto en la receta."""
        return self.cantidad * self.producto.costo


class ProduccionRealizada(TenantOwnedModel):
    receta = models.ForeignKey(
        Receta,
        on_delete=models.PROTECT,
        related_name="producciones",
        verbose_name="Receta",
    )
    cantidad_lotes = models.DecimalField(
        "Cantidad de lotes",
        max_digits=10,
        decimal_places=2,
        default=Decimal("1"),
        help_text="Cuántas veces se ejecuta la receta. Ej: 2 = doble de ingredientes, doble de rendimiento.",
    )
    fecha = models.DateTimeField("Fecha de producción", default=timezone.now)
    observaciones = models.TextField("Observaciones", blank=True)

    class Meta:
        verbose_name = "Producción realizada"
        verbose_name_plural = "Producciones realizadas"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.receta} × {self.cantidad_lotes} lote(s) — {self.fecha:%d/%m/%Y}"

    @property
    def cantidad_producida(self) -> Decimal:
        return self.receta.rendimiento * self.cantidad_lotes

    @property
    def costo_total_estimado(self) -> Decimal:
        return self.receta.costo_total * self.cantidad_lotes
