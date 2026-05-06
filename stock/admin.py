from django.contrib import admin

from core.admin import TenantOwnedAdmin

from .models import MovimientoStock, Producto


@admin.register(Producto)
class ProductoAdmin(TenantOwnedAdmin):
    list_display = (
        "nombre",
        "codigo",
        "unidad_medida",
        "stock_actual",
        "stock_minimo",
        "precio_venta",
        "activo",
    )
    list_filter = ("activo", "unidad_medida")
    search_fields = ("nombre", "codigo")
    fieldsets = (
        ("Identificación", {"fields": ("nombre", "codigo", "presentacion", "unidad_medida", "activo")}),
        ("Stock", {"fields": ("stock_actual", "stock_minimo")}),
        ("Precios", {"fields": ("costo", "precio_venta")}),
    )
    readonly_fields = ("stock_actual",)


@admin.register(MovimientoStock)
class MovimientoStockAdmin(TenantOwnedAdmin):
    list_display = ("fecha", "producto", "tipo", "cantidad", "motivo")
    list_filter = ("tipo", "fecha")
    search_fields = ("producto__nombre", "motivo")
    autocomplete_fields = ("producto",)
    fieldsets = (
        (None, {"fields": ("producto", "tipo", "cantidad", "motivo")}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            obj.aplicar_a_stock()
