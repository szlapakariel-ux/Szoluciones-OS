from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MovimientoStock
from .servicios import crear_unidades_cerradas


@receiver(post_save, sender=MovimientoStock)
def aplicar_movimiento_a_stock(sender, instance: MovimientoStock, created, **kwargs):
    if not created:
        return
    instance.aplicar_a_stock()
    # Los ingresos de venta (reversas de items borrados) reponen unidades
    # físicas explícitamente vía stock.servicios.revertir_*; acá solo se
    # auto-generan unidades cerradas para ingresos de compra/producción.
    if (
        instance.tipo == MovimientoStock.Tipo.INGRESO
        and not instance.venta_origen_id
        and instance.producto.porciones_por_unidad > 1
    ):
        crear_unidades_cerradas(instance.producto, instance.cantidad)
