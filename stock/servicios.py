"""Lógica de fraccionamiento de unidades físicas (tortas, budines, etc.).

Un producto con `porciones_por_unidad` > 1 se rastrea con `UnidadFisica`:
cada unidad entera (torta) es CERRADA hasta que se le vende una porción, momento
en el que pasa a ABIERTA con `porciones_restantes` decreciendo; al llegar a 0
queda AGOTADA. Vender "entera" exige una unidad CERRADA — si en el mostrador
solo quedan unidades ABIERTA (todas ya fraccionadas), la venta de una entera
debe rechazarse aunque la suma de porciones sueltas alcance para más de una.
"""
from django.db import transaction

from .models import EstadoUnidadFisica, UnidadFisica


class StockInsuficienteError(Exception):
    pass


def crear_unidades_cerradas(producto, cantidad):
    """Da de alta `cantidad` unidades físicas nuevas y cerradas (ingreso por
    compra o producción)."""
    cantidad = int(cantidad)
    if cantidad <= 0:
        return []
    return UnidadFisica.objects.bulk_create([
        UnidadFisica(negocio=producto.negocio, producto=producto, estado=EstadoUnidadFisica.CERRADA)
        for _ in range(cantidad)
    ])


@transaction.atomic
def consumir_entera(producto):
    """Consume una unidad CERRADA completa. Lanza StockInsuficienteError si
    no hay ninguna disponible (por ejemplo, si todo lo que queda en el
    mostrador son unidades ya abiertas)."""
    unidad = (
        UnidadFisica.objects.select_for_update()
        .filter(producto=producto, estado=EstadoUnidadFisica.CERRADA)
        .first()
    )
    if not unidad:
        raise StockInsuficienteError(
            f"No hay unidades cerradas de {producto} disponibles para vender enteras."
        )
    unidad.estado = EstadoUnidadFisica.AGOTADA
    unidad.porciones_restantes = 0
    unidad.save(update_fields=["estado", "porciones_restantes"])
    return unidad


def consumir_enteras(producto, cantidad):
    return [consumir_entera(producto) for _ in range(int(cantidad))]


@transaction.atomic
def _abrir_unidad(producto):
    unidad = (
        UnidadFisica.objects.select_for_update()
        .filter(producto=producto, estado=EstadoUnidadFisica.CERRADA)
        .first()
    )
    if not unidad:
        raise StockInsuficienteError(
            f"No hay unidades cerradas de {producto} para abrir y fraccionar."
        )
    unidad.estado = EstadoUnidadFisica.ABIERTA
    unidad.porciones_restantes = producto.porciones_por_unidad
    unidad.save(update_fields=["estado", "porciones_restantes"])
    return unidad


@transaction.atomic
def consumir_porciones(producto, porciones):
    """Descuenta `porciones` del mostrador, usando primero unidades ya abiertas
    (la de menos porciones restantes primero, para agotarlas) y abriendo
    unidades cerradas nuevas si hace falta. Lanza StockInsuficienteError si
    no alcanza el stock físico."""
    restante = int(porciones)
    unidades_afectadas = []
    while restante > 0:
        unidad = (
            UnidadFisica.objects.select_for_update()
            .filter(producto=producto, estado=EstadoUnidadFisica.ABIERTA)
            .order_by("porciones_restantes")
            .first()
        )
        if not unidad:
            unidad = _abrir_unidad(producto)
        tomar = min(restante, unidad.porciones_restantes)
        unidad.porciones_restantes -= tomar
        unidad.estado = (
            EstadoUnidadFisica.AGOTADA if unidad.porciones_restantes == 0
            else EstadoUnidadFisica.ABIERTA
        )
        unidad.save(update_fields=["estado", "porciones_restantes"])
        unidades_afectadas.append(unidad)
        restante -= tomar
    return unidades_afectadas


@transaction.atomic
def revertir_entera(producto):
    """Repone una unidad entera cerrada (reversa de una venta 'entera')."""
    return crear_unidades_cerradas(producto, 1)[0]


@transaction.atomic
def revertir_porciones(producto, porciones):
    """Repone `porciones` sueltas: las suma a una unidad abierta existente (sin
    superar su capacidad) o abre una nueva a partir de una cerrada; si no hay
    ninguna cerrada para reabrir, crea una unidad abierta nueva directamente
    con esas porciones."""
    restante = int(porciones)
    porciones_por_unidad = producto.porciones_por_unidad
    while restante > 0:
        unidad = (
            UnidadFisica.objects.select_for_update()
            .filter(producto=producto, estado=EstadoUnidadFisica.ABIERTA)
            .order_by("-porciones_restantes")
            .first()
        )
        if unidad and unidad.porciones_restantes < porciones_por_unidad:
            devolver = min(restante, porciones_por_unidad - unidad.porciones_restantes)
            unidad.porciones_restantes += devolver
            unidad.save(update_fields=["porciones_restantes"])
            restante -= devolver
            continue
        devolver = min(restante, porciones_por_unidad)
        UnidadFisica.objects.create(
            negocio=producto.negocio,
            producto=producto,
            estado=EstadoUnidadFisica.ABIERTA,
            porciones_restantes=devolver,
        )
        restante -= devolver
