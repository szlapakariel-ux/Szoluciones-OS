from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST


@login_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def producto_rapido(request):
    """Carga rápida de un producto desde el POS, sin necesidad de stock inicial."""
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from stock.models import Producto, TipoProducto, UnidadMedida

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

        producto = Producto.objects.create(
            negocio=negocio,
            nombre=nombre,
            presentacion=presentacion,
            unidad_medida=unidad,
            precio_venta=precio,
            tipo=TipoProducto.VENTA,
        )

        cart = request.session.get("cart", [])
        cart.append({
            "producto_id": producto.pk,
            "nombre": producto.nombre,
            "precio": str(producto.precio_venta),
            "cantidad": "1",
            "unidad": producto.unidad_corta,
        })
        request.session["cart"] = cart

        messages.success(request, f"'{nombre}' agregado al carrito. Cargá el stock cuando puedas.")
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

    from stock.models import Producto, TipoProducto

    qs = (
        Producto.objects.all_tenants()
        .filter(negocio=negocio, activo=True)
        .order_by("nombre")
    )

    productos = list(qs)
    for p in productos:
        p.bajo_stock = p.stock_actual < p.stock_minimo

    sin_clasificar = [p for p in productos if p.tipo is None]
    de_venta = [p for p in productos if p.tipo == TipoProducto.VENTA]
    insumos = [p for p in productos if p.tipo == TipoProducto.INSUMO]

    alerta_count = sum(1 for p in productos if p.bajo_stock)

    return render(request, "app/stock.html", {
        "active_tab": "stock",
        "sin_clasificar": sin_clasificar,
        "de_venta": de_venta,
        "insumos": insumos,
        "alerta_count": alerta_count,
        "total": len(productos),
    })


@require_POST
@login_required(login_url="/admin/login/")
def producto_clasificar(request, pk):
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from stock.models import Producto, TipoProducto

    tipo = request.POST.get("tipo")
    valid_tipos = {c[0] for c in TipoProducto.choices}
    if tipo not in valid_tipos:
        messages.error(request, "Tipo inválido.")
        return redirect("app_stock")

    producto = get_object_or_404(
        Producto.objects.all_tenants().filter(negocio=negocio), pk=pk
    )
    producto.tipo = tipo
    producto.save(update_fields=["tipo"])

    label = "venta" if tipo == TipoProducto.VENTA else "insumo"
    messages.success(request, f"'{producto.nombre}' marcado como {label}.")
    return redirect("app_stock")
