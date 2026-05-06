from decimal import Decimal

from django.contrib import admin
from unfold.admin import TabularInline

from caja.models import MovimientoCaja
from core.admin import TenantOwnedAdmin

from .models import Compra, ItemCompra, Proveedor


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


@admin.register(Compra)
class CompraAdmin(TenantOwnedAdmin):
    list_display = ("fecha", "proveedor", "total", "items_count")
    list_filter = ("fecha", "proveedor")
    search_fields = ("proveedor__nombre", "observaciones")
    autocomplete_fields = ("proveedor",)
    date_hierarchy = "fecha"
    inlines = [ItemCompraInline]
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
