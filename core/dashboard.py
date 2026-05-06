from datetime import timedelta
from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone


def _format_ars(amount: Decimal) -> str:
    s = f"{amount:,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


def dashboard_callback(request, context):
    """KPIs simples para la home del admin de Szoluciones OS."""
    context["kpis"] = []
    if not request.user.is_authenticated or not request.user.negocio_id:
        return context

    from caja.models import MovimientoCaja
    from stock.models import Producto
    from ventas.models import Venta

    negocio = request.user.negocio
    hoy = timezone.localdate()
    inicio_semana = hoy - timedelta(days=hoy.weekday())

    ventas_hoy = Venta.objects.all_tenants().filter(
        negocio=negocio, fecha__date=hoy
    )
    ventas_hoy_total = ventas_hoy.aggregate(t=Sum("total"))["t"] or Decimal("0")

    movs = MovimientoCaja.objects.all_tenants().filter(negocio=negocio)
    ingresos = movs.filter(tipo="INGRESO").aggregate(t=Sum("monto"))["t"] or Decimal("0")
    egresos = movs.filter(tipo="EGRESO").aggregate(t=Sum("monto"))["t"] or Decimal("0")
    caja_actual = ingresos - egresos

    productos_bajo_stock = (
        Producto.objects.all_tenants()
        .filter(negocio=negocio, stock_actual__lt=F("stock_minimo"))
        .count()
    )

    context["kpis"] = [
        {
            "title": "Ventas de hoy",
            "metric": _format_ars(ventas_hoy_total),
            "footer": f"{ventas_hoy.count()} venta(s) hoy",
        },
        {
            "title": "Caja actual",
            "metric": _format_ars(caja_actual),
            "footer": "Ingresos − egresos acumulados",
        },
        {
            "title": "Productos bajo stock mínimo",
            "metric": str(productos_bajo_stock),
            "footer": "Reponer pronto",
        },
        {
            "title": "Semana en curso",
            "metric": inicio_semana.strftime("%d/%m"),
            "footer": "Lunes de esta semana",
        },
    ]
    return context
