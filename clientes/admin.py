from django.contrib import admin

from core.admin import TenantOwnedAdmin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(TenantOwnedAdmin):
    list_display = ("nombre", "telefono", "email", "fecha_alta")
    search_fields = ("nombre", "telefono", "email")
    list_filter = ("fecha_alta",)
    fieldsets = (
        ("Datos principales", {"fields": ("nombre", "cumpleanios")}),
        ("Contacto", {"fields": ("telefono", "email", "direccion")}),
        ("Notas", {"fields": ("notas",)}),
    )
