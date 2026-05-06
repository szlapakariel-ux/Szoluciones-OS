import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import render
from django.utils import timezone


_MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _fmt(amount):
    if amount is None:
        amount = Decimal("0")
    s = f"{Decimal(amount):,.2f}"
    return "$" + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_short(amount):
    """Formato compacto: $12.500 en lugar de $12.500,00"""
    if amount is None:
        amount = Decimal("0")
    n = int(amount)
    if n >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if n >= 1_000:
        s = f"{n:,}".replace(",", ".")
        return f"${s}"
    return f"${n}"


@login_required(login_url="/admin/login/")
def app_home(request):
    ctx = {"active_tab": "home", "tiene_datos": False}

    if not request.user.negocio_id:
        return render(request, "app/home.html", ctx)

    from stock.models import Producto
    from ventas.models import ItemVenta, Venta

    negocio = request.user.negocio
    hoy = timezone.localdate()

    # Rango mes actual y anterior
    mes_inicio = hoy.replace(day=1)
    mes_ant_fin = mes_inicio - timedelta(days=1)
    mes_ant_inicio = mes_ant_fin.replace(day=1)

    # --- Ventas mes actual ---
    qs_mes = Venta.objects.all_tenants().filter(negocio=negocio, fecha__date__gte=mes_inicio)
    total_mes = qs_mes.aggregate(t=Sum("total"))["t"] or Decimal("0")
    count_mes = qs_mes.count()

    # --- Ventas mes anterior ---
    total_ant = (
        Venta.objects.all_tenants()
        .filter(negocio=negocio, fecha__date__gte=mes_ant_inicio, fecha__date__lte=mes_ant_fin)
        .aggregate(t=Sum("total"))["t"]
        or Decimal("0")
    )

    # Variación porcentual
    cambio_pct = None
    cambio_positivo = True
    if total_ant > 0:
        cambio_pct = float((total_mes - total_ant) / total_ant * 100)
        cambio_positivo = cambio_pct >= 0

    # Ticket promedio del mes
    ticket_promedio = (total_mes / count_mes) if count_mes > 0 else Decimal("0")

    # --- Ventas de hoy ---
    qs_hoy = Venta.objects.all_tenants().filter(negocio=negocio, fecha__date=hoy)
    total_hoy = qs_hoy.aggregate(t=Sum("total"))["t"] or Decimal("0")
    count_hoy = qs_hoy.count()

    # --- Sparkline: últimos 7 días ---
    hace_7 = hoy - timedelta(days=6)
    ventas_7d = (
        Venta.objects.all_tenants()
        .filter(negocio=negocio, fecha__date__gte=hace_7)
        .annotate(dia=TruncDate("fecha"))
        .values("dia")
        .annotate(total=Sum("total"))
        .order_by("dia")
    )
    dias_dict = {v["dia"]: float(v["total"]) for v in ventas_7d}
    spark_labels, spark_data = [], []
    for i in range(7):
        dia = hace_7 + timedelta(days=i)
        spark_labels.append(dia.strftime("%d/%m"))
        spark_data.append(dias_dict.get(dia, 0))

    # --- Top 3 productos del mes ---
    top_raw = (
        ItemVenta.objects.all_tenants()
        .filter(negocio=negocio, venta__fecha__date__gte=mes_inicio)
        .values("producto__nombre")
        .annotate(total=Sum("cantidad"))
        .order_by("-total")[:3]
    )
    top_productos = [{"nombre": p["producto__nombre"], "total": p["total"]} for p in top_raw]

    # --- Productos bajo stock ---
    bajo_stock = (
        Producto.objects.all_tenants()
        .filter(negocio=negocio, stock_actual__lt=F("stock_minimo"))
        .count()
    )

    tiene_datos = count_mes > 0 or total_ant > 0

    empty_previews = [
        "Tu facturación del mes, de un vistazo",
        "Cuánto creció tu negocio vs el mes anterior",
        "Tus productos más vendidos",
        "Tu ticket promedio y cantidad de ventas",
        "Alertas de stock para no quedarte sin mercadería",
    ]

    ctx.update({
        "empty_previews": empty_previews,
        "tiene_datos": tiene_datos,
        "mes_nombre": f"{_MESES[hoy.month - 1]} {hoy.year}",
        "total_mes_fmt": _fmt_short(total_mes),
        "total_mes_completo": _fmt(total_mes),
        "cambio_pct": round(cambio_pct, 1) if cambio_pct is not None else None,
        "cambio_positivo": cambio_positivo,
        "count_mes": count_mes,
        "ticket_promedio_fmt": _fmt_short(ticket_promedio),
        "total_hoy_fmt": _fmt_short(total_hoy),
        "count_hoy": count_hoy,
        "top_productos": top_productos,
        "bajo_stock": bajo_stock,
        "spark_json": json.dumps({"labels": spark_labels, "data": spark_data}),
    })

    return render(request, "app/home.html", ctx)
