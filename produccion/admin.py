from django.contrib import admin
from unfold.admin import TabularInline

from core.admin import TenantOwnedAdmin

from .models import Ingrediente, Receta


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
