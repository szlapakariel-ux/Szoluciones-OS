from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


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
