from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Negocio, Usuario
from stock.models import Producto, TipoProducto
from ventas.models import ItemVenta, Venta


def _negocio(nombre="TestNegocio"):
    return Negocio.objects.create(nombre=nombre)


def _usuario(negocio, username="testuser"):
    u = Usuario.objects.create_user(username=username, password="pass", negocio=negocio)
    return u


def _producto(negocio, nombre, codigo="", precio=Decimal("100"), activo=True):
    return Producto.objects.all_tenants().create(
        negocio=negocio,
        nombre=nombre,
        codigo=codigo,
        tipo=TipoProducto.VENTA,
        precio_venta=precio,
        stock_actual=Decimal("10"),
        activo=activo,
    )


def _venta_hace(negocio, producto, dias):
    fecha = timezone.now() - timedelta(days=dias)
    v = Venta.objects.all_tenants().create(negocio=negocio, fecha=fecha, total=Decimal("0"))
    ItemVenta.objects.all_tenants().create(
        negocio=negocio,
        venta=v,
        producto=producto,
        cantidad=Decimal("1"),
        precio_unitario=producto.precio_venta,
    )
    return v


class VentaRapidaSearchTests(TestCase):
    def setUp(self):
        self.negocio = _negocio()
        self.user = _usuario(self.negocio)
        self.client = Client()
        self.client.force_login(self.user)
        self.url = reverse("app_venta")

    # --- búsqueda por nombre ---

    def test_busqueda_parcial_nombre(self):
        _producto(self.negocio, "Alfajor triple")
        _producto(self.negocio, "Leche entera")
        resp = self.client.get(self.url, {"q": "alfajor"})
        self.assertEqual(resp.status_code, 200)
        nombres = [p.nombre for p in resp.context["productos"]]
        self.assertIn("Alfajor triple", nombres)
        self.assertNotIn("Leche entera", nombres)

    def test_busqueda_case_insensitive(self):
        _producto(self.negocio, "Yerba Mate")
        resp = self.client.get(self.url, {"q": "YERBA"})
        nombres = [p.nombre for p in resp.context["productos"]]
        self.assertIn("Yerba Mate", nombres)

    def test_termino_conservado_en_contexto(self):
        resp = self.client.get(self.url, {"q": "hola"})
        self.assertEqual(resp.context["q"], "hola")

    def test_q_vacio_no_filtra(self):
        _producto(self.negocio, "Producto A")
        _producto(self.negocio, "Producto B")
        resp = self.client.get(self.url, {"q": ""})
        self.assertEqual(len(resp.context["productos"]), 2)

    # --- búsqueda por código ---

    def test_busqueda_por_codigo(self):
        _producto(self.negocio, "Aceite girasol", codigo="ACE001")
        _producto(self.negocio, "Sal fina", codigo="SAL002")
        resp = self.client.get(self.url, {"q": "ACE"})
        nombres = [p.nombre for p in resp.context["productos"]]
        self.assertIn("Aceite girasol", nombres)
        self.assertNotIn("Sal fina", nombres)

    # --- aislamiento de negocio e inactivos ---

    def test_otro_negocio_excluido(self):
        otro = _negocio("OtroNegocio")
        _producto(otro, "Producto foráneo")
        _producto(self.negocio, "Producto propio")
        resp = self.client.get(self.url, {"q": "Producto"})
        nombres = [p.nombre for p in resp.context["productos"]]
        self.assertIn("Producto propio", nombres)
        self.assertNotIn("Producto foráneo", nombres)

    def test_inactivo_excluido(self):
        _producto(self.negocio, "Activo")
        _producto(self.negocio, "Inactivo", activo=False)
        resp = self.client.get(self.url)
        nombres = [p.nombre for p in resp.context["productos"]]
        self.assertNotIn("Inactivo", nombres)

    # --- orden por frecuencia 30 días ---

    def test_mas_apariciones_primero(self):
        p1 = _producto(self.negocio, "Arroz")
        p2 = _producto(self.negocio, "Azúcar")
        _venta_hace(self.negocio, p2, dias=1)
        _venta_hace(self.negocio, p2, dias=2)
        _venta_hace(self.negocio, p1, dias=3)
        resp = self.client.get(self.url)
        productos = resp.context["productos"]
        self.assertEqual(productos[0].nombre, "Azúcar")
        self.assertEqual(productos[1].nombre, "Arroz")

    def test_empate_orden_alfabetico(self):
        p1 = _producto(self.negocio, "Zapallo")
        p2 = _producto(self.negocio, "Avena")
        _venta_hace(self.negocio, p1, dias=1)
        _venta_hace(self.negocio, p2, dias=2)
        resp = self.client.get(self.url)
        productos = resp.context["productos"]
        self.assertEqual(productos[0].nombre, "Avena")
        self.assertEqual(productos[1].nombre, "Zapallo")

    def test_sin_ventas_al_final(self):
        p_con = _producto(self.negocio, "Con venta")
        p_sin = _producto(self.negocio, "Sin venta")
        _venta_hace(self.negocio, p_con, dias=1)
        resp = self.client.get(self.url)
        productos = resp.context["productos"]
        self.assertEqual(productos[0].nombre, "Con venta")
        self.assertEqual(productos[1].nombre, "Sin venta")

    # --- ventana temporal de 30 días ---

    def test_venta_31_dias_no_cuenta(self):
        p_vieja = _producto(self.negocio, "Azúcar")
        p_nueva = _producto(self.negocio, "Arroz")
        _venta_hace(self.negocio, p_vieja, dias=31)
        _venta_hace(self.negocio, p_nueva, dias=1)
        resp = self.client.get(self.url)
        productos = resp.context["productos"]
        self.assertEqual(productos[0].nombre, "Arroz")

    # --- estado vacío ---

    def test_vacio_sin_busqueda(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "No hay productos cargados")

    def test_vacio_con_busqueda(self):
        _producto(self.negocio, "Leche")
        resp = self.client.get(self.url, {"q": "xyz"})
        self.assertContains(resp, "Sin resultados para")

    # --- sin historial → orden alfabético ---

    def test_sin_historial_orden_alfabetico(self):
        _producto(self.negocio, "Zanahoria")
        _producto(self.negocio, "Apio")
        _producto(self.negocio, "Manzana")
        resp = self.client.get(self.url)
        nombres = [p.nombre for p in resp.context["productos"]]
        self.assertEqual(nombres, sorted(nombres))

    # --- agregar al carrito sigue funcionando con búsqueda ---

    def test_agregar_producto_con_busqueda_activa(self):
        p = _producto(self.negocio, "Manteca")
        resp = self.client.post(
            reverse("app_venta_agregar"),
            {"producto_id": p.pk, "cantidad": "2"},
        )
        self.assertRedirects(resp, self.url)
        cart = self.client.session.get("cart", [])
        self.assertEqual(len(cart), 1)
        self.assertEqual(cart[0]["nombre"], "Manteca")
