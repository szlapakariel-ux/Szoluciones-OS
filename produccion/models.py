from decimal import Decimal

from django.db import models

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
        help_text="Cantidad de producto resultante que produce esta receta.",
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
            (i.cantidad * i.producto.costo for i in self.ingredientes.all()),
            Decimal("0"),
        )

    @property
    def costo_unitario(self) -> Decimal:
        if self.rendimiento and self.rendimiento > 0:
            return self.costo_total / self.rendimiento
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
        return f"{self.producto} × {self.cantidad}"
