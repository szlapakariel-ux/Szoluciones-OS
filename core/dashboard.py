import json
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone


def _format_ars(amount: Decimal) -> str:
    s = f"{amount:,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


_METODO_LABELS = {
    "EFECTIVO": "Efectivo",
    "DEBITO": "Débito",
    "CREDITO": "Crédito",
    "TRANSFERENCIA": "Transferencia",
    "MP": "Mercado Pago",
    "OTRO": "Otro",
}


def dashboard_callback(request, context):
    """KPIs y datos de gráficos para la home del admin."""
    context["kpis"] = []
    context["charts"] = None
    if not request.user.is_authenticated or not request.user.negocio_id:
        return context

    from caja.models import MovimientoCaja
    from stock.models import Producto
    from ventas.models import ItemVenta, Venta

    negocio = request.user.negocio
    hoy = timezone.localdate()
    inicio_semana = hoy - timedelta(days=hoy.weekday())

    # --- KPIs ---
    ventas_hoy = Venta.objects.all_tenants().filter(negocio=negocio, fecha__date=hoy)
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

    # --- Chart 1: Ventas últimos 7 días ---
    hace_7_dias = hoy - timedelta(days=6)
    ventas_7d_qs = (
        Venta.objects.all_tenants()
        .filter(negocio=negocio, fecha__date__gte=hace_7_dias)
        .annotate(dia=TruncDate("fecha"))
        .values("dia")
        .annotate(total=Sum("total"))
        .order_by("dia")
    )
    dias_dict = {v["dia"]: float(v["total"]) for v in ventas_7d_qs}
    labels_dias, data_dias = [], []
    for i in range(7):
        dia = hace_7_dias + timedelta(days=i)
        labels_dias.append(dia.strftime("%d/%m"))
        data_dias.append(dias_dict.get(dia, 0))

    # --- Chart 2: Top 5 productos más vendidos (por unidades) ---
    top_qs = (
        ItemVenta.objects.all_tenants()
        .filter(negocio=negocio)
        .values("producto__nombre")
        .annotate(total_qty=Sum("cantidad"))
        .order_by("-total_qty")[:5]
    )
    labels_productos = [p["producto__nombre"] for p in top_qs]
    data_productos = [float(p["total_qty"]) for p in top_qs]

    # --- Chart 3: Mix de métodos de pago ---
    metodos_qs = (
        Venta.objects.all_tenants()
        .filter(negocio=negocio)
        .values("metodo_pago")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    labels_metodos = [_METODO_LABELS.get(m["metodo_pago"], m["metodo_pago"]) for m in metodos_qs]
    data_metodos = [m["count"] for m in metodos_qs]

    context["charts"] = json.dumps({
        "ventasDias": {"labels": labels_dias, "data": data_dias},
        "topProductos": {"labels": labels_productos, "data": data_productos},
        "metodosPago": {"labels": labels_metodos, "data": data_metodos},
    })

    return context
