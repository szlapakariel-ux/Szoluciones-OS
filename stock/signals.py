from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MovimientoStock


@receiver(post_save, sender=MovimientoStock)
def aplicar_movimiento_a_stock(sender, instance: MovimientoStock, created, **kwargs):
    if not created:
        return
    instance.aplicar_a_stock()
