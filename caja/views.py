from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone


def _fmt(amount):
    if amount is None:
        amount = Decimal("0")
    s = f"{Decimal(amount):,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


@login_required(login_url="/admin/login/")
def caja_dia(request):
    negocio = getattr(request.user, "negocio", None)
    if not negocio:
        return redirect("/admin/")

    from caja.models import MovimientoCaja

    movs = MovimientoCaja.objects.all_tenants().filter(negocio=negocio)
    ing_total = movs.filter(tipo="INGRESO").aggregate(t=Sum("monto"))["t"] or Decimal("0")
    egr_total = movs.filter(tipo="EGRESO").aggregate(t=Sum("monto"))["t"] or Decimal("0")

    hoy = timezone.localdate()
    movs_hoy = movs.filter(fecha__date=hoy)
    ing_hoy = movs_hoy.filter(tipo="INGRESO").aggregate(t=Sum("monto"))["t"] or Decimal("0")
    egr_hoy = movs_hoy.filter(tipo="EGRESO").aggregate(t=Sum("monto"))["t"] or Decimal("0")

    ultimos = movs.order_by("-fecha")[:20]

    return render(request, "app/caja.html", {
        "active_tab": "caja",
        "saldo_fmt": _fmt(ing_total - egr_total),
        "ingresos_hoy_fmt": _fmt(ing_hoy),
        "egresos_hoy_fmt": _fmt(egr_hoy),
        "movimientos": ultimos,
    })
