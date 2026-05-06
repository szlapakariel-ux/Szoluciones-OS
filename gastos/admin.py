from django.contrib import admin

from core.admin import TenantOwnedAdmin

from .models import GastoFijo


@admin.register(GastoFijo)
class GastoFijoAdmin(TenantOwnedAdmin):
    list_display = ("concepto", "monto", "periodicidad", "proximo_vencimiento", "activo")
    list_filter = ("periodicidad", "activo")
    search_fields = ("concepto",)
    fieldsets = (
        ("Datos principales", {"fields": ("concepto", "monto", "activo")}),
        ("Periodicidad", {"fields": ("periodicidad", "proximo_vencimiento")}),
        ("Notas", {"fields": ("notas",)}),
    )
