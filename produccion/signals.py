from django.db.models.signals import post_save
from django.dispatch import receiver

from stock.models import MovimientoStock

from .models import ProduccionRealizada


@receiver(post_save, sender=ProduccionRealizada)
def produccion_realizada_post_save(sender, instance: ProduccionRealizada, created, **kwargs):
    if not created:
        return
    receta = instance.receta
    lotes = instance.cantidad_lotes
    motivo = f"Producción #{instance.pk} — {receta.nombre}"

    for ingrediente in receta.ingredientes.select_related("producto").all():
        MovimientoStock.objects.create(
            negocio=instance.negocio,
            producto=ingrediente.producto,
            tipo=MovimientoStock.Tipo.EGRESO,
            cantidad=ingrediente.cantidad * lotes,
            motivo=motivo,
            fecha=instance.fecha,
            produccion_origen=instance,
        )

    MovimientoStock.objects.create(
        negocio=instance.negocio,
        producto=receta.producto_resultante,
        tipo=MovimientoStock.Tipo.INGRESO,
        cantidad=receta.rendimiento * lotes,
        motivo=motivo,
        fecha=instance.fecha,
        produccion_origen=instance,
    )
