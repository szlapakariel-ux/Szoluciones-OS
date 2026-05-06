from decimal import Decimal

from django.db import models

from core.models import TenantOwnedModel
from stock.models import Producto


class Proveedor(TenantOwnedModel):
    nombre = models.CharField("Nombre", max_length=120)
    telefono = models.CharField("Teléfono", max_length=40, blank=True)
    email = models.EmailField("Email", blank=True)
    cuit = models.CharField("CUIT", max_length=20, blank=True)
    direccion = models.CharField("Dirección", max_length=200, blank=True)
    notas = models.TextField("Notas", blank=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Compra(TenantOwnedModel):
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.PROTECT,
        related_name="compras",
        verbose_name="Proveedor",
    )
    fecha = models.DateTimeField("Fecha")
    total = models.DecimalField(
        "Total", max_digits=12, decimal_places=2, default=Decimal("0")
    )
    observaciones = models.TextField("Observaciones", blank=True)

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Compra a {self.proveedor} · {self.fecha:%d/%m/%Y}"

    def recalcular_total(self):
        total = sum(
            (item.cantidad * item.precio_unitario for item in self.items.all()),
            Decimal("0"),
        )
        Compra.objects.all_tenants().filter(pk=self.pk).update(total=total)
        self.total = total


class ItemCompra(TenantOwnedModel):
    compra = models.ForeignKey(
        Compra,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Compra",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="items_compra",
        verbose_name="Producto",
    )
    cantidad = models.DecimalField("Cantidad", max_digits=12, decimal_places=2)
    precio_unitario = models.DecimalField(
        "Precio unitario", max_digits=12, decimal_places=2
    )

    class Meta:
        verbose_name = "Ítem de compra"
        verbose_name_plural = "Ítems de compra"

    def __str__(self):
        return f"{self.producto} × {self.cantidad}"

    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.precio_unitario
