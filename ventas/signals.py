from decimal import Decimal

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from stock.models import MovimientoStock
from stock.servicios import consumir_enteras, consumir_porciones, revertir_entera, revertir_porciones

from .models import ItemVenta


def _cantidad_stock(instance: ItemVenta):
    """Unidades físicas a descontar: cantidad × factor de la presentación (o 1 si no hay)."""
    if instance.presentacion_id:
        return instance.cantidad * instance.presentacion.factor
    return instance.cantidad


def _partir_en_enteras_y_porciones(producto, cantidad_stock):
    """Traduce una cantidad de stock (posiblemente fraccionaria, ej: factor 0.5
    de una PresentacionVenta "Media") a (unidades enteras, porciones sueltas),
    para poder consumir/revertir contra UnidadFisica de forma granular."""
    porciones_por_unidad = producto.porciones_por_unidad
    enteras = int(cantidad_stock)
    resto = cantidad_stock - enteras
    porciones = int((resto * porciones_por_unidad).to_integral_value())
    return enteras, porciones


def _egresar(negocio, producto, venta, cantidad_stock, motivo):
    if producto.porciones_por_unidad > 1:
        enteras, porciones = _partir_en_enteras_y_porciones(producto, cantidad_stock)
        if enteras:
            consumir_enteras(producto, enteras)
        if porciones:
            consumir_porciones(producto, porciones)
    MovimientoStock.objects.create(
        negocio=negocio,
        producto=producto,
        tipo=MovimientoStock.Tipo.EGRESO,
        cantidad=cantidad_stock,
        motivo=motivo,
        venta_origen=venta,
    )


def _egresar_porciones(negocio, producto, venta, porciones, motivo):
    consumir_porciones(producto, porciones)
    cantidad_stock = Decimal(porciones) / producto.porciones_por_unidad
    MovimientoStock.objects.create(
        negocio=negocio,
        producto=producto,
        tipo=MovimientoStock.Tipo.EGRESO,
        cantidad=cantidad_stock,
        motivo=motivo,
        venta_origen=venta,
    )


def _ingresar(negocio, producto, venta, cantidad_stock, motivo):
    if producto.porciones_por_unidad > 1:
        enteras, porciones = _partir_en_enteras_y_porciones(producto, cantidad_stock)
        for _ in range(enteras):
            revertir_entera(producto)
        if porciones:
            revertir_porciones(producto, porciones)
    MovimientoStock.objects.create(
        negocio=negocio,
        producto=producto,
        tipo=MovimientoStock.Tipo.INGRESO,
        cantidad=cantidad_stock,
        motivo=motivo,
        venta_origen=venta,
    )


def _ingresar_porciones(negocio, producto, venta, porciones, motivo):
    revertir_porciones(producto, porciones)
    cantidad_stock = Decimal(porciones) / producto.porciones_por_unidad
    MovimientoStock.objects.create(
        negocio=negocio,
        producto=producto,
        tipo=MovimientoStock.Tipo.INGRESO,
        cantidad=cantidad_stock,
        motivo=motivo,
        venta_origen=venta,
    )


@receiver(post_save, sender=ItemVenta)
def itemventa_post_save(sender, instance: ItemVenta, created, **kwargs):
    if not created:
        return

    if instance.combo_id:
        combo = instance.combo
        motivo = f"Combo {combo.nombre} — Venta #{instance.venta_id}"
        for ci in combo.items.select_related("producto").all():
            if ci.porciones:
                total_porciones = ci.porciones * instance.cantidad
                _egresar_porciones(instance.negocio, ci.producto, instance.venta, total_porciones, motivo)
            else:
                cantidad_stock = Decimal(ci.cantidad) * instance.cantidad
                _egresar(instance.negocio, ci.producto, instance.venta, cantidad_stock, motivo)
        return

    if instance.porciones:
        motivo = f"Venta #{instance.venta_id}"
        total_porciones = instance.porciones * instance.cantidad
        _egresar_porciones(instance.negocio, instance.producto, instance.venta, total_porciones, motivo)
        return

    _egresar(
        instance.negocio, instance.producto, instance.venta,
        _cantidad_stock(instance), f"Venta #{instance.venta_id}",
    )


@receiver(post_delete, sender=ItemVenta)
def itemventa_post_delete(sender, instance: ItemVenta, **kwargs):
    if instance.combo_id:
        combo = instance.combo
        motivo = f"Reversa por borrado de ítem de venta #{instance.venta_id} (combo {combo.nombre})"
        for ci in combo.items.select_related("producto").all():
            if ci.porciones:
                total_porciones = ci.porciones * instance.cantidad
                _ingresar_porciones(instance.negocio, ci.producto, instance.venta, total_porciones, motivo)
            else:
                cantidad_stock = Decimal(ci.cantidad) * instance.cantidad
                _ingresar(instance.negocio, ci.producto, instance.venta, cantidad_stock, motivo)
        return

    if instance.porciones:
        motivo = f"Reversa por borrado de ítem de venta #{instance.venta_id}"
        total_porciones = instance.porciones * instance.cantidad
        _ingresar_porciones(instance.negocio, instance.producto, instance.venta, total_porciones, motivo)
        return

    _ingresar(
        instance.negocio, instance.producto, instance.venta,
        _cantidad_stock(instance),
        f"Reversa por borrado de ítem de venta #{instance.venta_id}",
    )
