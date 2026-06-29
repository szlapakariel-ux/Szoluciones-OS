from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from stock.models import MovimientoStock

from .models import ItemVenta


def _cantidad_stock(instance: ItemVenta):
    """Unidades físicas a descontar: cantidad × factor de la presentación (o 1 si no hay)."""
    if instance.presentacion_id:
        return instance.cantidad * instance.presentacion.factor
    return instance.cantidad


@receiver(post_save, sender=ItemVenta)
def itemventa_post_save(sender, instance: ItemVenta, created, **kwargs):
    if not created:
        return
    MovimientoStock.objects.create(
        negocio=instance.negocio,
        producto=instance.producto,
        tipo=MovimientoStock.Tipo.EGRESO,
        cantidad=_cantidad_stock(instance),
        motivo=f"Venta #{instance.venta_id}",
        venta_origen=instance.venta,
    )


@receiver(post_delete, sender=ItemVenta)
def itemventa_post_delete(sender, instance: ItemVenta, **kwargs):
    MovimientoStock.objects.create(
        negocio=instance.negocio,
        producto=instance.producto,
        tipo=MovimientoStock.Tipo.INGRESO,
        cantidad=_cantidad_stock(instance),
        motivo=f"Reversa por borrado de ítem de venta #{instance.venta_id}",
        venta_origen=instance.venta,
    )
