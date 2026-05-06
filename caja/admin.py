from django.contrib import admin

from core.admin import TenantOwnedAdmin

from .models import MovimientoCaja


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(TenantOwnedAdmin):
    list_display = ("fecha", "tipo", "monto", "concepto", "metodo_pago")
    list_filter = ("tipo", "metodo_pago", "fecha")
    search_fields = ("concepto",)
    date_hierarchy = "fecha"
    fieldsets = (
        (None, {"fields": ("fecha", "tipo", "monto", "concepto", "metodo_pago")}),
        (
            "Origen automático",
            {
                "classes": ("collapse",),
                "fields": ("venta_origen", "compra_origen", "gasto_origen"),
            },
        ),
    )
    readonly_fields = ("venta_origen", "compra_origen", "gasto_origen")
