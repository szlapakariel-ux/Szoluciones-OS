from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from stock.models import MovimientoStock

from .models import ItemVenta


@receiver(post_save, sender=ItemVenta)
def itemventa_post_save(sender, instance: ItemVenta, created, **kwargs):
    if not created:
        return
    MovimientoStock.objects.create(
        negocio=instance.negocio,
        producto=instance.producto,
        tipo=MovimientoStock.Tipo.EGRESO,
        cantidad=instance.cantidad,
        motivo=f"Venta #{instance.venta_id}",
        venta_origen=instance.venta,
    )


@receiver(post_delete, sender=ItemVenta)
def itemventa_post_delete(sender, instance: ItemVenta, **kwargs):
    MovimientoStock.objects.create(
        negocio=instance.negocio,
        producto=instance.producto,
        tipo=MovimientoStock.Tipo.INGRESO,
        cantidad=instance.cantidad,
        motivo=f"Reversa por borrado de ítem de venta #{instance.venta_id}",
        venta_origen=instance.venta,
    )
