from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Permission
from unfold.admin import ModelAdmin, TabularInline

from .models import ActividadNegocio, Negocio, Usuario


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

    # Trial freeze: si el trial venció, el negocio queda en solo-lectura
    def has_add_permission(self, request):
        if getattr(request, "negocio_frozen", False):
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if getattr(request, "negocio_frozen", False):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if getattr(request, "negocio_frozen", False):
            return False
        return super().has_delete_permission(request, obj)


class ActividadNegocioInline(TabularInline):
    model = ActividadNegocio
    extra = 0
    max_num = 0
    fields = ("fecha", "modulo", "accion")
    readonly_fields = ("fecha", "modulo", "accion")
    can_delete = False
    tab = True
    ordering = ("-fecha",)
    verbose_name = "Actividad reciente"
    verbose_name_plural = "Actividad reciente"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Negocio)
class NegocioAdmin(ModelAdmin):
    list_display = ("nombre", "rubro", "telefono", "fecha_alta", "activo", "trial_hasta")
    list_filter = ("activo", "rubro")
    search_fields = ("nombre", "cuit", "telefono")
    inlines = [ActividadNegocioInline]
    fieldsets = (
        ("Datos principales", {"fields": ("nombre", "rubro")}),
        ("Contacto", {"fields": ("telefono", "direccion", "cuit")}),
        (
            "Módulos habilitados",
            {
                "fields": ("modulo_produccion", "modulo_clientes", "modulo_compras", "modulo_gastos"),
                "description": "Activá o desactivá los módulos disponibles para este negocio.",
            },
        ),
        (
            "Trial y estado",
            {
                "fields": ("activo", "trial_hasta"),
                "description": "Dejá 'Trial hasta' vacío para acceso sin restricción de tiempo.",
            },
        ),
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

    @admin.action(description="Activar como usuario de negocio (staff + permisos)")
    def activar_staff(self, request, queryset):
        perms = Permission.objects.filter(
            content_type__app_label__in=[
                "stock", "compras", "clientes", "ventas",
                "produccion", "caja", "gastos",
            ]
        )
        count = 0
        for user in queryset.filter(is_superuser=False):
            user.is_staff = True
            user.save(update_fields=["is_staff"])
            user.user_permissions.set(perms)
            count += 1
        self.message_user(request, f"{count} usuario(s) activados como staff con permisos operativos.")

    actions = ["activar_staff"]

    def save_model(self, request, obj, form, change):
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
