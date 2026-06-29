from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST


def _fmt(amount):
    if amount is None:
        amount = Decimal("0")
    s = f"{Decimal(amount):,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


@login_required(login_url="/admin/login/")
def venta_rapida(request):
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from caja.models import MovimientoCaja
    from stock.models import Producto

    cart = request.session.get("cart", [])
    total = sum(
        Decimal(str(i["precio"])) * Decimal(str(i["cantidad"])) for i in cart
    )
    for item in cart:
        subtotal = Decimal(str(item["precio"])) * Decimal(str(item["cantidad"]))
        item["subtotal_fmt"] = _fmt(subtotal)

    from stock.models import TipoProducto

    q = request.GET.get("q", "").strip()
    fecha_desde = timezone.now() - timedelta(days=30)

    productos_qs = (
        Producto.objects.all_tenants()
        .filter(negocio=negocio, activo=True, tipo=TipoProducto.VENTA)
        .annotate(
            frecuencia_30d=Count(
                "items_venta",
                filter=Q(items_venta__venta__fecha__gte=fecha_desde),
                distinct=True,
            )
        )
        .order_by("-frecuencia_30d", "nombre")
    )

    if q:
        productos_qs = productos_qs.filter(
            Q(nombre__icontains=q) | Q(codigo__icontains=q)
        )

    productos_list = list(productos_qs)
    sin_stock = [p for p in productos_list if p.stock_actual < 0]

    return render(request, "app/venta.html", {
        "active_tab": "venta",
        "cart": cart,
        "total_fmt": _fmt(total),
        "productos": productos_list,
        "sin_stock": sin_stock,
        "metodos_pago": MovimientoCaja.MetodoPago.choices,
        "q": q,
    })


@require_POST
@login_required(login_url="/admin/login/")
def venta_agregar(request):
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from stock.models import Producto

    producto_id = request.POST.get("producto_id")
    cantidad_raw = request.POST.get("cantidad", "1")

    try:
        cantidad = Decimal(cantidad_raw.replace(",", "."))
        if cantidad <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        messages.error(request, "Cantidad inválida.")
        return redirect("app_venta")

    try:
        producto = Producto.objects.all_tenants().get(pk=producto_id, negocio=negocio)
    except Producto.DoesNotExist:
        messages.error(request, "Producto no encontrado.")
        return redirect("app_venta")

    cart = request.session.get("cart", [])
    for item in cart:
        if item["producto_id"] == producto.pk:
            item["cantidad"] = str(Decimal(str(item["cantidad"])) + cantidad)
            break
    else:
        cart.append({
            "producto_id": producto.pk,
            "nombre": producto.nombre,
            "precio": str(producto.precio_venta),
            "cantidad": str(cantidad),
            "unidad": producto.unidad_corta,
        })
    request.session["cart"] = cart
    return redirect("app_venta")


@require_POST
@login_required(login_url="/admin/login/")
def venta_quitar(request, idx):
    cart = request.session.get("cart", [])
    if 0 <= idx < len(cart):
        cart.pop(idx)
        request.session["cart"] = cart
    return redirect("app_venta")


@require_POST
@login_required(login_url="/admin/login/")
def venta_confirmar(request):
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    cart = request.session.get("cart", [])
    if not cart:
        messages.error(request, "El carrito está vacío.")
        return redirect("app_venta")

    from caja.models import MovimientoCaja
    from ventas.models import ItemVenta, Venta

    metodo_pago = request.POST.get("metodo_pago", MovimientoCaja.MetodoPago.EFECTIVO)
    valid_methods = {c[0] for c in MovimientoCaja.MetodoPago.choices}
    if metodo_pago not in valid_methods:
        metodo_pago = MovimientoCaja.MetodoPago.EFECTIVO

    try:
        venta = Venta.objects.create(
            negocio=negocio,
            fecha=timezone.now(),
            metodo_pago=metodo_pago,
            total=Decimal("0"),
        )
        for item in cart:
            ItemVenta.objects.create(
                negocio=negocio,
                venta=venta,
                producto_id=item["producto_id"],
                cantidad=Decimal(str(item["cantidad"])),
                precio_unitario=Decimal(str(item["precio"])),
            )
        venta.recalcular_total()
        MovimientoCaja.objects.create(
            negocio=negocio,
            tipo=MovimientoCaja.Tipo.INGRESO,
            monto=venta.total,
            concepto=f"Venta #{venta.pk}",
            metodo_pago=metodo_pago,
            venta_origen=venta,
            fecha=venta.fecha,
        )
        request.session["cart"] = []
        messages.success(request, f"Venta #{venta.pk} registrada por {_fmt(venta.total)}.")
    except Exception as exc:
        messages.error(request, f"Error al guardar la venta: {exc}")

    return redirect("app_venta")
