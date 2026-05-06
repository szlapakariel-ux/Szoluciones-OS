from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.shortcuts import render
from django.utils import timezone


def _fmt(amount):
    if amount is None:
        amount = Decimal("0")
    s = f"{Decimal(amount):,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


@login_required(login_url="/admin/login/")
def app_home(request):
    kpis = []
    if request.user.negocio_id:
        from caja.models import MovimientoCaja
        from stock.models import Producto
        from ventas.models import Venta

        negocio = request.user.negocio
        hoy = timezone.localdate()
        inicio_semana = hoy - timedelta(days=hoy.weekday())

        ventas_hoy = Venta.objects.all_tenants().filter(negocio=negocio, fecha__date=hoy)
        total_hoy = ventas_hoy.aggregate(t=Sum("total"))["t"] or Decimal("0")

        movs = MovimientoCaja.objects.all_tenants().filter(negocio=negocio)
        ing = movs.filter(tipo="INGRESO").aggregate(t=Sum("monto"))["t"] or Decimal("0")
        egr = movs.filter(tipo="EGRESO").aggregate(t=Sum("monto"))["t"] or Decimal("0")

        bajo_stock = (
            Producto.objects.all_tenants()
            .filter(negocio=negocio, stock_actual__lt=F("stock_minimo"))
            .count()
        )

        kpis = [
            {"title": "Ventas hoy", "metric": _fmt(total_hoy), "footer": f"{ventas_hoy.count()} venta(s)"},
            {"title": "Caja actual", "metric": _fmt(ing - egr), "footer": "Ingresos − egresos"},
            {"title": "Bajo stock", "metric": str(bajo_stock), "footer": "Productos a reponer"},
            {"title": "Semana desde", "metric": inicio_semana.strftime("%d/%m"), "footer": "Lunes de esta semana"},
        ]

    return render(request, "app/home.html", {"kpis": kpis, "active_tab": "home"})
