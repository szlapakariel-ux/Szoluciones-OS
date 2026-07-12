from decimal import Decimal, InvalidOperation

from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse

from unfold.admin import TabularInline

from core.admin import TenantOwnedAdmin
from ventas.models import PresentacionVenta

from .forms import EditarProductosMasivoForm
from .models import MovimientoStock, Producto, UnidadFisica


def _fmt(amount):
    s = f"{amount:,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


class PresentacionVentaInline(TabularInline):
    model = PresentacionVenta
    extra = 1
    fields = ("nombre", "factor", "precio", "activo")


@admin.register(Producto)
class ProductoAdmin(TenantOwnedAdmin):
    list_display = (
        "nombre",
        "tipo",
        "codigo",
        "unidad_medida",
        "stock_actual",
        "stock_minimo",
        "precio_venta",
        "activo",
    )
    list_filter = ("tipo", "activo", "unidad_medida")
    search_fields = ("nombre", "codigo")
    fieldsets = (
        ("Identificación", {"fields": ("nombre", "tipo", "codigo", "presentacion", "unidad_medida", "activo")}),
        ("Stock", {"fields": ("stock_actual", "stock_minimo", "porciones_por_unidad")}),
        ("Precios", {"fields": ("costo", "precio_venta", "cantidad_minima_mayorista", "precio_mayorista")}),
    )
    readonly_fields = ("stock_actual",)
    inlines = [PresentacionVentaInline]
    actions = ["editar_seleccionados"]

    @admin.action(description="Editar seleccionados/as")
    def editar_seleccionados(self, request, queryset):
        if "aplicar" in request.POST:
            form = EditarProductosMasivoForm(request.POST)
            if form.is_valid():
                cambios = form.campos_a_actualizar()
                if cambios:
                    cantidad = queryset.update(**cambios)
                    self.message_user(
                        request,
                        f"Se actualizaron {cantidad} producto(s): "
                        + ", ".join(f"{k}={v}" for k, v in cambios.items()),
                    )
                else:
                    self.message_user(request, "No se completó ningún campo — no se cambió nada.", messages.WARNING)
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = EditarProductosMasivoForm()

        return render(request, "admin/stock/producto/editar_seleccionados.html", {
            "productos": queryset,
            "form": form,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "opts": self.model._meta,
            "title": "Editar productos seleccionados",
        })

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "actualizar-costo/",
                self.admin_site.admin_view(self.actualizar_costo_view),
                name="stock_producto_actualizar_costo",
            ),
        ]
        return custom + urls

    def actualizar_costo_view(self, request):
        redirect_url = request.META.get("HTTP_REFERER") or reverse("admin:compras_compra_changelist")
        pk = request.GET.get("pk")
        nuevo_costo_str = request.GET.get("nuevo_costo")
        if pk and nuevo_costo_str:
            try:
                nuevo_costo = Decimal(nuevo_costo_str)
                qs = Producto.objects.all_tenants()
                if request.user.negocio_id:
                    qs = qs.filter(negocio=request.user.negocio)
                producto = qs.get(pk=pk)
                producto.costo = nuevo_costo
                producto.save(update_fields=["costo"])
                messages.success(
                    request,
                    f"Costo de {producto.nombre} actualizado a {_fmt(nuevo_costo)}.",
                )
            except (Producto.DoesNotExist, InvalidOperation, Exception):
                messages.error(request, "No se pudo actualizar el costo.")
        return HttpResponseRedirect(redirect_url)


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


@admin.register(UnidadFisica)
class UnidadFisicaAdmin(TenantOwnedAdmin):
    list_display = ("producto", "estado", "porciones_restantes", "actualizado_en")
    list_filter = ("estado",)
    search_fields = ("producto__nombre",)
    autocomplete_fields = ("producto",)
    readonly_fields = ("creado_en", "actualizado_en")
