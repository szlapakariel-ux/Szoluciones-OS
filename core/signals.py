from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ActividadNegocio


@receiver(post_save, sender="ventas.Venta")
def log_venta(sender, instance, created, **kwargs):
    if created:
        ActividadNegocio.objects.create(
            negocio=instance.negocio,
            modulo="ventas",
            accion="Se registró 1 venta",
        )


@receiver(post_save, sender="compras.Compra")
def log_compra(sender, instance, created, **kwargs):
    if created:
        ActividadNegocio.objects.create(
            negocio=instance.negocio,
            modulo="compras",
            accion="Se registró 1 compra",
        )


@receiver(post_save, sender="stock.Producto")
def log_producto(sender, instance, created, **kwargs):
    if created:
        ActividadNegocio.objects.create(
            negocio=instance.negocio,
            modulo="stock",
            accion="Se cargó 1 producto nuevo",
        )
