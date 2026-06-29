import logging
from functools import wraps

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ActividadNegocio

logger = logging.getLogger(__name__)


def _log(negocio, modulo, accion):
    """Registra una actividad de auditoría. Los errores se registran en el log
    técnico pero nunca interrumpen la operación principal."""
    if not negocio:
        return
    try:
        ActividadNegocio.objects.create(negocio=negocio, modulo=modulo, accion=accion[:200])
    except Exception:
        logger.exception(
            "Error al registrar actividad de auditoría [negocio=%s modulo=%s accion=%s]",
            getattr(negocio, "pk", negocio),
            modulo,
            accion[:200],
        )


def _safe(fn):
    """Activity-log signals must never break the save of the model they observe.

    Los errores se registran en el log técnico para que puedan diagnosticarse,
    pero no se propagan al caller ni al usuario final.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception(
                "Error inesperado en señal de auditoría [signal=%s]", fn.__name__
            )
            return None
    return wrapper


# --- Ventas ---

@receiver(post_save, sender="ventas.Venta")
@_safe
def log_venta_save(sender, instance, created, **kwargs):
    if created:
        _log(instance.negocio, "ventas", "Venta registrada")

@receiver(post_delete, sender="ventas.Venta")
@_safe
def log_venta_delete(sender, instance, **kwargs):
    _log(instance.negocio, "ventas", "Venta eliminada")


# --- Stock / Productos ---

@receiver(post_save, sender="stock.Producto")
@_safe
def log_producto_save(sender, instance, created, **kwargs):
    if created:
        _log(instance.negocio, "stock", f"Producto creado: {instance.nombre}")
    else:
        _log(instance.negocio, "stock", f"Producto editado: {instance.nombre}")

@receiver(post_delete, sender="stock.Producto")
@_safe
def log_producto_delete(sender, instance, **kwargs):
    _log(instance.negocio, "stock", f"Producto eliminado: {instance.nombre}")

@receiver(post_save, sender="stock.MovimientoStock")
@_safe
def log_movimiento_stock(sender, instance, created, **kwargs):
    if created:
        tipo = instance.get_tipo_display()
        _log(instance.negocio, "stock", f"Movimiento de stock: {tipo}")


# --- Compras ---

@receiver(post_save, sender="compras.Compra")
@_safe
def log_compra_save(sender, instance, created, **kwargs):
    if created:
        _log(instance.negocio, "compras", "Compra registrada")

@receiver(post_delete, sender="compras.Compra")
@_safe
def log_compra_delete(sender, instance, **kwargs):
    _log(instance.negocio, "compras", "Compra eliminada")

@receiver(post_save, sender="compras.Proveedor")
@_safe
def log_proveedor_save(sender, instance, created, **kwargs):
    if created:
        _log(instance.negocio, "compras", f"Proveedor creado: {instance.nombre}")


# --- Caja ---

@receiver(post_save, sender="caja.MovimientoCaja")
@_safe
def log_caja(sender, instance, created, **kwargs):
    if created:
        tipo = instance.get_tipo_display()
        _log(instance.negocio, "caja", f"Movimiento de caja: {tipo}")


# --- Producción ---

@receiver(post_save, sender="produccion.Receta")
@_safe
def log_receta_save(sender, instance, created, **kwargs):
    if created:
        _log(instance.negocio, "produccion", f"Receta creada: {instance.nombre}")
    else:
        _log(instance.negocio, "produccion", f"Receta editada: {instance.nombre}")

@receiver(post_save, sender="produccion.ProduccionRealizada")
@_safe
def log_produccion(sender, instance, created, **kwargs):
    if created:
        _log(instance.negocio, "produccion", "Producción ejecutada")


# --- Clientes ---

@receiver(post_save, sender="clientes.Cliente")
@_safe
def log_cliente_save(sender, instance, created, **kwargs):
    if created:
        _log(instance.negocio, "clientes", f"Cliente creado: {instance.nombre}")
    else:
        _log(instance.negocio, "clientes", f"Cliente editado: {instance.nombre}")

@receiver(post_delete, sender="clientes.Cliente")
@_safe
def log_cliente_delete(sender, instance, **kwargs):
    _log(instance.negocio, "clientes", f"Cliente eliminado: {instance.nombre}")


# --- Gastos ---

@receiver(post_save, sender="gastos.GastoFijo")
@_safe
def log_gasto_save(sender, instance, created, **kwargs):
    if created:
        _log(instance.negocio, "gastos", f"Gasto fijo creado: {instance.concepto}")

@receiver(post_delete, sender="gastos.GastoFijo")
@_safe
def log_gasto_delete(sender, instance, **kwargs):
    _log(instance.negocio, "gastos", f"Gasto fijo eliminado: {instance.concepto}")


# --- Acceso ---

@receiver(user_logged_in)
@_safe
def log_login(sender, request, user, **kwargs):
    negocio = getattr(user, "negocio", None)
    _log(negocio, "acceso", f"Inicio de sesión: {user.username}")

@receiver(user_logged_out)
@_safe
def log_logout(sender, request, user, **kwargs):
    if user:
        negocio = getattr(user, "negocio", None)
        _log(negocio, "acceso", f"Cierre de sesión: {user.username}")
