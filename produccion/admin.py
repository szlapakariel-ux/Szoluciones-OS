from django.contrib import admin
from django.utils.html import format_html, format_html_join
from unfold.admin import TabularInline

from core.admin import TenantOwnedAdmin
from stock.models import MovimientoStock

from .models import Ingrediente, ProduccionRealizada, Receta


def _fmt(amount):
    s = f"{amount:,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


class IngredienteInline(TabularInline):
    model = Ingrediente
    extra = 1
    fields = ("producto", "cantidad", "subtotal_display")
    readonly_fields = ("subtotal_display",)
    tab = True

    def subtotal_display(self, obj):
        if obj.pk and obj.producto_id:
            return format_html(
                '<span style="font-weight:600;color:#0d9488">{}</span>',
                _fmt(obj.costo_ingrediente),
            )
        return "—"

    subtotal_display.short_description = "Costo en receta"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "producto":
            from stock.models import Producto, TipoProducto
            kwargs["queryset"] = Producto.objects.filter(tipo=TipoProducto.INSUMO, activo=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Receta)
class RecetaAdmin(TenantOwnedAdmin):
    list_display = (
        "nombre",
        "producto_resultante",
        "rendimiento",
        "costo_unitario_display",
        "precio_venta_display",
        "precio_sugerido_display",
        "margen_display",
    )
    search_fields = ("nombre", "producto_resultante__nombre")
    autocomplete_fields = ("producto_resultante",)
    inlines = [IngredienteInline]
    readonly_fields = ("resumen_costos",)
    fieldsets = (
        (
            "Datos principales",
            {"fields": ("nombre", "producto_resultante", "rendimiento", "porcentaje_ganancia")},
        ),
        (
            "Resumen de costos",
            {"fields": ("resumen_costos",), "classes": ("wide",)},
        ),
        ("Instrucciones", {"fields": ("instrucciones",)}),
    )

    # ── list_display helpers ──────────────────────────────────────────────────

    def costo_unitario_display(self, obj):
        return _fmt(obj.costo_unitario)
    costo_unitario_display.short_description = "Costo unit."

    def precio_venta_display(self, obj):
        return _fmt(obj.producto_resultante.precio_venta)
    precio_venta_display.short_description = "Precio venta"

    def precio_sugerido_display(self, obj):
        return format_html(
            '<span style="color:#0d9488;font-weight:600">{}</span>',
            _fmt(obj.precio_sugerido),
        )
    precio_sugerido_display.short_description = "Precio sugerido"

    def margen_display(self, obj):
        pct = obj.margen_real_pct
        color = "#16a34a" if pct >= 20 else "#dc2626"
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            color, f"{pct:.1f}%",
        )
    margen_display.short_description = "Margen real"

    # ── panel CALCULAR ───────────────────────────────────────────────────────

    def resumen_costos(self, obj):
        if not obj.pk:
            return "Guardá la receta para ver el resumen."

        ingredientes = list(obj.ingredientes.select_related("producto").all())
        if not ingredientes:
            return "Sin ingredientes cargados."

        filas = format_html_join(
            "",
            (
                "<tr>"
                "<td style='padding:4px 10px'>{}</td>"
                "<td style='padding:4px 10px;text-align:right'>{}&nbsp;{}</td>"
                "<td style='padding:4px 10px;text-align:right;font-weight:600'>{}</td>"
                "</tr>"
            ),
            (
                (
                    ing.producto.nombre,
                    ing.cantidad,
                    ing.producto.get_unidad_medida_display(),
                    _fmt(ing.costo_ingrediente),
                )
                for ing in ingredientes
            ),
        )

        costo_total  = obj.costo_total
        costo_unit   = obj.costo_unitario
        precio_actual = obj.producto_resultante.precio_venta
        precio_sug   = obj.precio_sugerido
        margen       = obj.margen_real_pct
        ganancia_pct = obj.porcentaje_ganancia
        rendimiento  = obj.rendimiento
        unidad       = obj.producto_resultante.get_unidad_medida_display()
        margen_color = "#16a34a" if margen >= 20 else "#dc2626"

        return format_html(
            """
            <div style="font-family:inherit;max-width:540px">
              <table style="width:100%;border-collapse:collapse;
                            border:1px solid #e5e7eb;border-radius:6px;overflow:hidden;margin-bottom:14px">
                <thead>
                  <tr style="background:#f3f4f6">
                    <th style="padding:6px 10px;text-align:left;font-size:12px;color:#6b7280">Ingrediente</th>
                    <th style="padding:6px 10px;text-align:right;font-size:12px;color:#6b7280">Cantidad</th>
                    <th style="padding:6px 10px;text-align:right;font-size:12px;color:#6b7280">Precio en receta</th>
                  </tr>
                </thead>
                <tbody>{}</tbody>
              </table>

              <table style="width:100%;border-collapse:collapse">
                <tr>
                  <td style="padding:5px 0;color:#374151">Costo total del lote</td>
                  <td style="padding:5px 0;text-align:right;font-weight:600">{}</td>
                </tr>
                <tr>
                  <td style="padding:5px 0;color:#374151">Rendimiento</td>
                  <td style="padding:5px 0;text-align:right">{}&nbsp;{}</td>
                </tr>
                <tr style="border-top:1px solid #e5e7eb">
                  <td style="padding:7px 0;color:#111827;font-weight:700">Costo unitario</td>
                  <td style="padding:7px 0;text-align:right;font-weight:800;font-size:15px">{}</td>
                </tr>
                <tr style="border-top:1px solid #e5e7eb">
                  <td style="padding:5px 0;color:#374151">Precio de venta actual</td>
                  <td style="padding:5px 0;text-align:right">{}</td>
                </tr>
                <tr>
                  <td style="padding:5px 0;color:#374151">Margen bruto real</td>
                  <td style="padding:5px 0;text-align:right;font-weight:700;color:{}">{}&nbsp;%</td>
                </tr>
                <tr style="border-top:2px solid #0d9488;background:#f0fdf4">
                  <td style="padding:8px 0 8px 8px;color:#0d9488;font-weight:700">
                    Precio sugerido&nbsp;({}%&nbsp;ganancia)
                  </td>
                  <td style="padding:8px 8px 8px 0;text-align:right;font-weight:800;font-size:16px;color:#0d9488">{}</td>
                </tr>
              </table>
            </div>
            """,
            filas,
            _fmt(costo_total),
            rendimiento, unidad,
            _fmt(costo_unit),
            _fmt(precio_actual),
            margen_color, f"{margen:.1f}",
            ganancia_pct,
            _fmt(precio_sug),
        )

    resumen_costos.short_description = "Resumen de costos"


class MovimientoStockProduccionInline(TabularInline):
    model = MovimientoStock
    fk_name = "produccion_origen"
    extra = 0
    fields = ("producto", "tipo", "cantidad", "motivo")
    readonly_fields = ("producto", "tipo", "cantidad", "motivo")
    can_delete = False
    tab = True
    verbose_name = "Movimiento de stock"
    verbose_name_plural = "Movimientos de stock generados"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProduccionRealizada)
class ProduccionRealizadaAdmin(TenantOwnedAdmin):
    list_display = ("fecha", "receta", "cantidad_lotes", "cantidad_producida_display", "costo_display")
    list_filter = ("fecha", "receta")
    search_fields = ("receta__nombre", "observaciones")
    autocomplete_fields = ("receta",)
    date_hierarchy = "fecha"
    inlines = [MovimientoStockProduccionInline]
    readonly_fields = ("cantidad_producida_display", "costo_display")
    fieldsets = (
        ("Producción", {"fields": ("receta", "cantidad_lotes", "fecha")}),
        ("Resultado", {"fields": ("cantidad_producida_display", "costo_display")}),
        ("Notas", {"fields": ("observaciones",)}),
    )

    def cantidad_producida_display(self, obj):
        if obj.pk:
            return f"{obj.cantidad_producida} {obj.receta.producto_resultante.unidad_medida}"
        return "—"
    cantidad_producida_display.short_description = "Cantidad producida"

    def costo_display(self, obj):
        if obj.pk:
            return _fmt(obj.costo_total_estimado)
        return "—"
    costo_display.short_description = "Costo estimado"
