from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from stock.models import MovimientoStock

from .models import ItemCompra


@receiver(post_save, sender=ItemCompra)
def itemcompra_post_save(sender, instance: ItemCompra, created, **kwargs):
    if not created:
        return
    MovimientoStock.objects.create(
        negocio=instance.negocio,
        producto=instance.producto,
        tipo=MovimientoStock.Tipo.INGRESO,
        cantidad=instance.cantidad,
        motivo=f"Compra #{instance.compra_id}",
    )


@receiver(post_delete, sender=ItemCompra)
def itemcompra_post_delete(sender, instance: ItemCompra, **kwargs):
    MovimientoStock.objects.create(
        negocio=instance.negocio,
        producto=instance.producto,
        tipo=MovimientoStock.Tipo.EGRESO,
        cantidad=instance.cantidad,
        motivo=f"Reversa por borrado de ítem de compra #{instance.compra_id}",
    )
