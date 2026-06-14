from decimal import Decimal, InvalidOperation

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from core.admin import TenantOwnedAdmin

from .models import MovimientoStock, Producto


def _fmt(amount):
    s = f"{amount:,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


@admin.register(Producto)
class ProductoAdmin(TenantOwnedAdmin):
    list_display = (
        "nombre",
        "tipo",
        "codigo",
        "unidad_medida",
        "stock_actual",
        "stock_minimo",
        "costo",
        "precio_venta",
        "activo",
    )
    list_filter = ("tipo", "activo", "unidad_medida")
    search_fields = ("nombre", "codigo")
    fieldsets = (
        ("Identificación", {"fields": ("nombre", "tipo", "codigo", "presentacion", "unidad_medida", "activo")}),
        ("Stock", {"fields": ("stock_actual", "stock_minimo")}),
        ("Precios", {"fields": ("costo", "precio_venta")}),
    )
    readonly_fields = ("stock_actual",)

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
