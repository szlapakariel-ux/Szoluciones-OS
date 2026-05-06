from django.contrib import admin
from unfold.admin import TabularInline

from caja.models import MovimientoCaja
from core.admin import TenantOwnedAdmin
from stock.models import MovimientoStock

from .models import ItemVenta, Venta


class ItemVentaInline(TabularInline):
    model = ItemVenta
    extra = 1
    fields = ("producto", "cantidad", "precio_unitario")
    autocomplete_fields = ("producto",)
    tab = True


class MovimientoStockVentaInline(TabularInline):
    model = MovimientoStock
    fk_name = "venta_origen"
    extra = 0
    fields = ("producto", "tipo", "cantidad", "motivo", "fecha")
    readonly_fields = ("producto", "tipo", "cantidad", "motivo", "fecha")
    can_delete = False
    tab = True
    verbose_name = "Movimiento de stock"
    verbose_name_plural = "Movimientos de stock generados"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Venta)
class VentaAdmin(TenantOwnedAdmin):
    list_display = ("fecha", "cliente", "total", "metodo_pago", "items_count")
    list_filter = ("fecha", "metodo_pago")
    search_fields = ("cliente__nombre", "observaciones")
    autocomplete_fields = ("cliente",)
    date_hierarchy = "fecha"
    inlines = [ItemVentaInline, MovimientoStockVentaInline]
    readonly_fields = ("total",)
    fieldsets = (
        ("Datos de la venta", {"fields": ("cliente", "fecha", "metodo_pago")}),
        ("Total", {"fields": ("total",)}),
        ("Notas", {"fields": ("observaciones",)}),
    )

    def items_count(self, obj):
        return obj.items.count()

    items_count.short_description = "Ítems"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        venta: Venta = form.instance
        venta.recalcular_total()
        if venta.total > 0:
            mov_existente = MovimientoCaja.objects.all_tenants().filter(
                venta_origen=venta
            ).first()
            if mov_existente:
                mov_existente.monto = venta.total
                mov_existente.metodo_pago = venta.metodo_pago
                mov_existente.save(update_fields=["monto", "metodo_pago"])
            else:
                cliente_str = f" a {venta.cliente}" if venta.cliente else ""
                MovimientoCaja.objects.create(
                    negocio=venta.negocio,
                    tipo=MovimientoCaja.Tipo.INGRESO,
                    monto=venta.total,
                    concepto=f"Venta{cliente_str}",
                    metodo_pago=venta.metodo_pago,
                    venta_origen=venta,
                    fecha=venta.fecha,
                )
