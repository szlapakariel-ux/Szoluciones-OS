from decimal import Decimal, ROUND_HALF_UP

from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from unfold.admin import TabularInline

from caja.models import MovimientoCaja
from core.admin import TenantOwnedAdmin
from core.models import Negocio
from stock.models import MovimientoStock

from .models import Compra, ItemCompra, Proveedor


def _fmt(amount):
    s = f"{amount:,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


@admin.register(Proveedor)
class ProveedorAdmin(TenantOwnedAdmin):
    list_display = ("nombre", "telefono", "email", "cuit")
    search_fields = ("nombre", "cuit", "telefono", "email")
    fieldsets = (
        ("Datos principales", {"fields": ("nombre", "cuit")}),
        ("Contacto", {"fields": ("telefono", "email", "direccion")}),
        ("Notas", {"fields": ("notas",)}),
    )


class ItemCompraInline(TabularInline):
    model = ItemCompra
    extra = 1
    fields = ("producto", "cantidad", "precio_unitario")
    autocomplete_fields = ("producto",)
    tab = True


class MovimientoStockCompraInline(TabularInline):
    model = MovimientoStock
    fk_name = "compra_origen"
    extra = 0
    fields = ("producto", "tipo", "cantidad", "motivo", "fecha")
    readonly_fields = ("producto", "tipo", "cantidad", "motivo", "fecha")
    can_delete = False
    tab = True
    verbose_name = "Movimiento de stock"
    verbose_name_plural = "Movimientos de stock generados"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Compra)
class CompraAdmin(TenantOwnedAdmin):
    list_display = ("fecha", "proveedor", "total", "items_count")
    list_filter = ("fecha", "proveedor")
    search_fields = ("proveedor__nombre", "observaciones")
    autocomplete_fields = ("proveedor",)
    date_hierarchy = "fecha"
    inlines = [ItemCompraInline, MovimientoStockCompraInline]
    readonly_fields = ("total",)
    fieldsets = (
        ("Datos de la compra", {"fields": ("proveedor", "fecha", "observaciones")}),
        ("Total", {"fields": ("total",)}),
    )

    def items_count(self, obj):
        return obj.items.count()

    items_count.short_description = "Ítems"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        compra: Compra = form.instance
        compra.recalcular_total()
        if compra.total > 0:
            mov_existente = MovimientoCaja.objects.all_tenants().filter(
                compra_origen=compra
            ).first()
            if mov_existente:
                mov_existente.monto = compra.total
                mov_existente.save(update_fields=["monto"])
            else:
                MovimientoCaja.objects.create(
                    negocio=compra.negocio,
                    tipo=MovimientoCaja.Tipo.EGRESO,
                    monto=compra.total,
                    concepto=f"Compra a {compra.proveedor}",
                    compra_origen=compra,
                    fecha=compra.fecha,
                )

        # Actualización de costos según método configurado en el negocio
        try:
            metodo = getattr(
                compra.negocio, "metodo_costeo", Negocio.MetodoCosteo.MANUAL
            )
        except Exception:
            metodo = Negocio.MetodoCosteo.MANUAL

        for item in compra.items.select_related("producto").all():
            try:
                producto = item.producto
                if producto is None:
                    continue
                # Refrescar desde DB para obtener stock_actual actualizado por señal
                producto.refresh_from_db(fields=["costo", "stock_actual"])
                if item.precio_unitario == producto.costo:
                    continue

                if metodo == Negocio.MetodoCosteo.PPP:
                    # stock_actual ya fue actualizado por la señal de MovimientoStock;
                    # restamos item.cantidad para obtener el stock previo a esta compra.
                    stock_previo = max(
                        producto.stock_actual - item.cantidad, Decimal("0")
                    )
                    denominador = stock_previo + item.cantidad
                    if denominador > 0:
                        nuevo_costo = (
                            (
                                stock_previo * producto.costo
                                + item.cantidad * item.precio_unitario
                            )
                            / denominador
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    else:
                        nuevo_costo = item.precio_unitario
                    producto.costo = nuevo_costo
                    producto.save(update_fields=["costo"])
                    messages.info(
                        request,
                        f"{producto.nombre}: costo actualizado a {_fmt(nuevo_costo)} (PPP)",
                    )
                else:
                    try:
                        update_url = (
                            reverse("admin:stock_producto_actualizar_costo")
                            + f"?pk={producto.pk}&nuevo_costo={item.precio_unitario}"
                        )
                        messages.warning(
                            request,
                            format_html(
                                "{}: costo registrado {} → precio de esta compra {}. "
                                '<a href="{}">Actualizar costo</a>',
                                producto.nombre,
                                _fmt(producto.costo),
                                _fmt(item.precio_unitario),
                                update_url,
                            ),
                        )
                    except Exception:
                        messages.warning(
                            request,
                            f"{producto.nombre}: el precio de compra ({_fmt(item.precio_unitario)}) "
                            f"difiere del costo registrado ({_fmt(producto.costo)}).",
                        )
            except Exception:
                pass
