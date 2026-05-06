from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin

from .models import Negocio, Usuario


class TenantOwnedAdmin(ModelAdmin):
    """Base admin que filtra el queryset por el negocio del usuario logueado
    y completa el campo `negocio` automáticamente al guardar."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_authenticated and request.user.negocio_id:
            return qs.filter(negocio=request.user.negocio)
        if request.user.is_superuser:
            return qs
        return qs.none()

    def save_model(self, request, obj, form, change):
        if not getattr(obj, "negocio_id", None) and request.user.negocio_id:
            obj.negocio = request.user.negocio
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.negocio_id
            and hasattr(db_field.related_model, "negocio")
            and db_field.name != "negocio"
        ):
            kwargs["queryset"] = db_field.related_model._default_manager.all_tenants().filter(
                negocio=request.user.negocio
            ) if hasattr(db_field.related_model._default_manager, "all_tenants") else db_field.related_model._default_manager.filter(
                negocio=request.user.negocio
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Negocio)
class NegocioAdmin(ModelAdmin):
    list_display = ("nombre", "rubro", "telefono", "fecha_alta", "activo")
    list_filter = ("activo", "rubro")
    search_fields = ("nombre", "cuit", "telefono")
    fieldsets = (
        ("Datos principales", {"fields": ("nombre", "rubro", "activo")}),
        ("Contacto", {"fields": ("telefono", "direccion", "cuit")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.is_authenticated and request.user.negocio_id:
            return qs.filter(pk=request.user.negocio_id)
        return qs.none()


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ("username", "negocio", "first_name", "last_name", "is_staff")
    list_filter = ("is_staff", "is_superuser", "is_active", "negocio")
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "email")}),
        ("Negocio", {"fields": ("negocio",)}),
        (
            "Permisos",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2", "negocio"),
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.is_authenticated and request.user.negocio_id:
            return qs.filter(negocio=request.user.negocio)
        return qs.none()
