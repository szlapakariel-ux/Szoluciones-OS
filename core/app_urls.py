from django.urls import path

from caja.views import caja_dia
from core.views import app_home
from stock.views import producto_clasificar, producto_rapido, stock_lista
from ventas.views import (
    venta_agregar,
    venta_confirmar,
    venta_quitar,
    venta_rapida,
    venta_seleccionar_presentacion,
)

urlpatterns = [
    path("", app_home, name="app_home"),
    path("venta/", venta_rapida, name="app_venta"),
    path("venta/agregar/", venta_agregar, name="app_venta_agregar"),
    path("venta/quitar/<int:idx>/", venta_quitar, name="app_venta_quitar"),
    path("venta/confirmar/", venta_confirmar, name="app_venta_confirmar"),
    path("venta/presentacion/", venta_seleccionar_presentacion, name="app_venta_presentacion"),
    path("producto/nuevo/", producto_rapido, name="app_producto_rapido"),
    path("producto/<int:pk>/clasificar/", producto_clasificar, name="app_producto_clasificar"),
    path("caja/", caja_dia, name="app_caja"),
    path("stock/", stock_lista, name="app_stock"),
]
