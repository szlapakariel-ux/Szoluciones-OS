from django.contrib import admin
from unfold.admin import TabularInline

from core.admin import TenantOwnedAdmin
from stock.models import MovimientoStock

from .models import Ingrediente, ProduccionRealizada, Receta


class IngredienteInline(TabularInline):
    model = Ingrediente
    extra = 1
    fields = ("producto", "cantidad")
    autocomplete_fields = ("producto",)
    tab = True


@admin.register(Receta)
class RecetaAdmin(TenantOwnedAdmin):
    list_display = ("nombre", "producto_resultante", "rendimiento", "costo_unitario_display")
    search_fields = ("nombre", "producto_resultante__nombre")
    autocomplete_fields = ("producto_resultante",)
    inlines = [IngredienteInline]
    fieldsets = (
        ("Datos principales", {"fields": ("nombre", "producto_resultante", "rendimiento")}),
        ("Instrucciones", {"fields": ("instrucciones",)}),
    )

    def costo_unitario_display(self, obj):
        return f"${obj.costo_unitario:.2f}"

    costo_unitario_display.short_description = "Costo unitario"


class MovimientoStockProduccionInline(TabularInline):
    model = MovimientoStock
    fk_name = "produccion_origen"
    extra = 0
    fields = ("producto", "tipo", "cantidad", "motivo")
    readonly_fields = ("producto", "tipo", "cantidad", "motivo")
    can_delete = False
    tab = True
    verbose_name = "Movimiento de stock"
    verbose_name_plural = "Movimientos de stock generados"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProduccionRealizada)
class ProduccionRealizadaAdmin(TenantOwnedAdmin):
    list_display = ("fecha", "receta", "cantidad_lotes", "cantidad_producida_display", "costo_display")
    list_filter = ("fecha", "receta")
    search_fields = ("receta__nombre", "observaciones")
    autocomplete_fields = ("receta",)
    date_hierarchy = "fecha"
    inlines = [MovimientoStockProduccionInline]
    readonly_fields = ("cantidad_producida_display", "costo_display")
    fieldsets = (
        ("Producción", {"fields": ("receta", "cantidad_lotes", "fecha")}),
        ("Resultado", {"fields": ("cantidad_producida_display", "costo_display")}),
        ("Notas", {"fields": ("observaciones",)}),
    )

    def cantidad_producida_display(self, obj):
        if obj.pk:
            return f"{obj.cantidad_producida} {obj.receta.producto_resultante.unidad_medida}"
        return "—"

    cantidad_producida_display.short_description = "Cantidad producida"

    def costo_display(self, obj):
        if obj.pk:
            return f"${obj.costo_total_estimado:.2f}"
        return "—"

    costo_display.short_description = "Costo estimado"
