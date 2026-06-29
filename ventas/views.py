from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
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
    from stock.models import Producto, TipoProducto
    from ventas.models import PresentacionVenta

    cart = request.session.get("cart", [])
    total = sum(
        Decimal(str(i["precio"])) * Decimal(str(i["cantidad"])) for i in cart
    )
    for item in cart:
        subtotal = Decimal(str(item["precio"])) * Decimal(str(item["cantidad"]))
        item["subtotal_fmt"] = _fmt(subtotal)

    productos = (
        Producto.objects.all_tenants()
        .filter(negocio=negocio, activo=True, tipo=TipoProducto.VENTA)
        .prefetch_related(
            Prefetch(
                "presentaciones",
                queryset=PresentacionVenta.objects.all_tenants().filter(
                    activo=True, negocio=negocio
                ).order_by("factor"),
                to_attr="presentaciones_activas",
            )
        )
        .annotate(total_vendido=Coalesce(Sum("items_venta__cantidad"), Value(Decimal("0"))))
        .order_by("-total_vendido", "nombre")
    )

    productos_list = list(productos)
    sin_stock = [p for p in productos_list if p.stock_actual < 0]

    return render(request, "app/venta.html", {
        "active_tab": "venta",
        "cart": cart,
        "total_fmt": _fmt(total),
        "productos": productos_list,
        "sin_stock": sin_stock,
        "metodos_pago": MovimientoCaja.MetodoPago.choices,
    })


@require_POST
@login_required(login_url="/admin/login/")
def venta_agregar(request):
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from stock.models import Producto
    from ventas.models import PresentacionVenta

    producto_id = request.POST.get("producto_id")
    cantidad_raw = request.POST.get("cantidad", "1")
    presentacion_id_raw = request.POST.get("presentacion_id", "").strip()

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

    presentacion = None
    presentacion_id = None

    if presentacion_id_raw:
        try:
            presentacion = PresentacionVenta.objects.all_tenants().get(
                pk=presentacion_id_raw,
                producto=producto,
                negocio=negocio,
                activo=True,
            )
            presentacion_id = presentacion.pk
        except PresentacionVenta.DoesNotExist:
            messages.error(request, "Presentación no válida.")
            return redirect("app_venta")
    else:
        tiene_presentaciones = PresentacionVenta.objects.all_tenants().filter(
            producto=producto, negocio=negocio, activo=True
        ).exists()
        if tiene_presentaciones:
            return redirect(
                reverse("app_venta_presentacion")
                + f"?producto_id={producto.pk}&cantidad={cantidad}"
            )

    precio = str(presentacion.precio) if presentacion else str(producto.precio_venta)
    presentacion_nombre = presentacion.nombre if presentacion else None

    cart = request.session.get("cart", [])
    for item in cart:
        if (
            item["producto_id"] == producto.pk
            and item.get("presentacion_id") == presentacion_id
        ):
            item["cantidad"] = str(Decimal(str(item["cantidad"])) + cantidad)
            break
    else:
        cart.append({
            "producto_id": producto.pk,
            "nombre": producto.nombre,
            "precio": precio,
            "cantidad": str(cantidad),
            "unidad": producto.unidad_corta,
            "presentacion_id": presentacion_id,
            "presentacion_nombre": presentacion_nombre,
        })
    request.session["cart"] = cart
    return redirect("app_venta")


@login_required(login_url="/admin/login/")
def venta_seleccionar_presentacion(request):
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from stock.models import Producto
    from ventas.models import PresentacionVenta

    producto_id = request.GET.get("producto_id")
    cantidad_raw = request.GET.get("cantidad", "1")

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

    presentaciones = list(
        PresentacionVenta.objects.all_tenants().filter(
            producto=producto, negocio=negocio, activo=True
        ).order_by("factor")
    )

    if not presentaciones:
        messages.error(request, "Este producto no tiene presentaciones activas.")
        return redirect("app_venta")

    return render(request, "app/venta_presentacion.html", {
        "active_tab": "venta",
        "producto": producto,
        "presentaciones": presentaciones,
        "cantidad": str(cantidad),
    })


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
    from ventas.models import ItemVenta, PresentacionVenta, Venta

    metodo_pago = request.POST.get("metodo_pago", MovimientoCaja.MetodoPago.EFECTIVO)
    valid_methods = {c[0] for c in MovimientoCaja.MetodoPago.choices}
    if metodo_pago not in valid_methods:
        metodo_pago = MovimientoCaja.MetodoPago.EFECTIVO

    try:
        with transaction.atomic():
            venta = Venta.objects.create(
                negocio=negocio,
                fecha=timezone.now(),
                metodo_pago=metodo_pago,
                total=Decimal("0"),
            )
            for item in cart:
                presentacion_id = item.get("presentacion_id")
                if presentacion_id is not None:
                    try:
                        PresentacionVenta.objects.all_tenants().get(
                            pk=presentacion_id,
                            producto_id=item["producto_id"],
                            negocio=negocio,
                            activo=True,
                        )
                    except PresentacionVenta.DoesNotExist:
                        raise ValueError(
                            f"Presentación inválida para '{item.get('nombre', 'producto')}'."
                        )
                ItemVenta.objects.create(
                    negocio=negocio,
                    venta=venta,
                    producto_id=item["producto_id"],
                    presentacion_id=presentacion_id,
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
