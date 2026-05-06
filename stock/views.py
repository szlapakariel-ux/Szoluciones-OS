from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


@login_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def producto_rapido(request):
    """Carga rápida de un producto desde el POS, sin necesidad de stock inicial."""
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from stock.models import Producto, UnidadMedida

    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        presentacion = (request.POST.get("presentacion") or "").strip()
        unidad = request.POST.get("unidad_medida") or UnidadMedida.UNIDAD
        precio_raw = (request.POST.get("precio_venta") or "0").replace(",", ".")

        if not nombre:
            messages.error(request, "El nombre es obligatorio.")
            return redirect("app_producto_rapido")

        try:
            precio = Decimal(precio_raw)
            if precio < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            messages.error(request, "Precio inválido.")
            return redirect("app_producto_rapido")

        valid_unidades = {c[0] for c in UnidadMedida.choices}
        if unidad not in valid_unidades:
            unidad = UnidadMedida.UNIDAD

        Producto.objects.create(
            negocio=negocio,
            nombre=nombre,
            presentacion=presentacion,
            unidad_medida=unidad,
            precio_venta=precio,
        )
        messages.success(request, f"Producto '{nombre}' creado. Cargá el stock cuando puedas.")
        return redirect("app_venta")

    return render(request, "app/producto_rapido.html", {
        "active_tab": "venta",
        "unidades": UnidadMedida.choices,
    })


@login_required(login_url="/admin/login/")
def stock_lista(request):
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from stock.models import Producto

    qs = (
        Producto.objects.all_tenants()
        .filter(negocio=negocio, activo=True)
        .order_by("nombre")
    )

    productos = list(qs)
    for p in productos:
        p.bajo_stock = p.stock_actual < p.stock_minimo

    alerta_count = sum(1 for p in productos if p.bajo_stock)

    return render(request, "app/stock.html", {
        "active_tab": "stock",
        "productos": productos,
        "alerta_count": alerta_count,
    })
