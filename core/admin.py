from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Permission
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
                "description": (
                    "Al crear un usuario con un Negocio asignado, "
                    "automaticamente se marca como staff y se le dan permisos "
                    "para operar todos los modulos de su negocio."
                ),
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

    def save_model(self, request, obj, form, change):
        # Onboarding 1-click: cuando se crea un usuario con un negocio
        # asignado, lo marcamos como staff y le damos los permisos
        # operativos del negocio. Asi alcanza con username + password +
        # negocio para que el cliente pueda loguearse y trabajar.
        is_new_with_negocio = (
            not change
            and obj.negocio_id
            and not obj.is_superuser
        )
        if is_new_with_negocio:
            obj.is_staff = True
        super().save_model(request, obj, form, change)
        if is_new_with_negocio:
            perms = Permission.objects.filter(
                content_type__app_label__in=[
                    "stock", "compras", "clientes", "ventas",
                    "produccion", "caja", "gastos",
                ]
            )
            obj.user_permissions.set(perms)
