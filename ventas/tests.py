from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Negocio
from stock.models import Producto, TipoProducto

from .models import PresentacionVenta

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _negocio(nombre="Negocio Test"):
    return Negocio.objects.create(nombre=nombre)


def _superusuario(negocio, username="admin_pv"):
    user = User.objects.create_superuser(
        username=username,
        password="testpass123",
        email=f"{username}@test.com",
    )
    user.negocio = negocio
    user.save(update_fields=["negocio"])
    return user


def _producto(negocio, nombre="Factura", tipo=None):
    if tipo is None:
        tipo = TipoProducto.VENTA
    return Producto.objects.all_tenants().create(
        negocio=negocio,
        nombre=nombre,
        tipo=tipo,
        costo=Decimal("50"),
        precio_venta=Decimal("100"),
    )


def _presentacion(negocio, producto, nombre="Unidad", factor="1.00", precio="100.00"):
    return PresentacionVenta.objects.all_tenants().create(
        negocio=negocio,
        producto=producto,
        nombre=nombre,
        factor=Decimal(factor),
        precio=Decimal(precio),
    )


# ---------------------------------------------------------------------------
# A. Creación válida
# ---------------------------------------------------------------------------

class PresentacionVentaCreacionTest(TestCase):
    def setUp(self):
        self.negocio = _negocio()
        self.producto = _producto(self.negocio)

    def test_crea_presentacion_basica(self):
        pv = _presentacion(self.negocio, self.producto)
        self.assertEqual(pv.nombre, "Unidad")
        self.assertEqual(pv.factor, Decimal("1.00"))
        self.assertEqual(pv.precio, Decimal("100.00"))
        self.assertTrue(pv.activo)

    def test_negocio_se_hereda_del_producto(self):
        pv = PresentacionVenta.objects.all_tenants().create(
            producto=self.producto,
            nombre="Media docena",
            factor=Decimal("6"),
            precio=Decimal("550"),
        )
        self.assertEqual(pv.negocio_id, self.producto.negocio_id)

    def test_multiples_presentaciones_mismo_producto(self):
        _presentacion(self.negocio, self.producto, "Unidad", "1.00", "100")
        _presentacion(self.negocio, self.producto, "Media docena", "6.00", "550")
        _presentacion(self.negocio, self.producto, "Docena", "12.00", "1000")
        self.assertEqual(
            PresentacionVenta.objects.all_tenants().filter(producto=self.producto).count(),
            3,
        )

    def test_str(self):
        pv = _presentacion(self.negocio, self.producto, "Unidad")
        self.assertIn("Unidad", str(pv))
        self.assertIn(self.producto.nombre, str(pv))

    def test_presentacion_inactiva(self):
        pv = PresentacionVenta.objects.all_tenants().create(
            negocio=self.negocio,
            producto=self.producto,
            nombre="Inactiva",
            factor=Decimal("1"),
            precio=Decimal("0"),
            activo=False,
        )
        self.assertFalse(pv.activo)

    def test_precio_cero_valido(self):
        pv = _presentacion(self.negocio, self.producto, "Gratis", "1.00", "0.00")
        pv.full_clean()
        self.assertEqual(pv.precio, Decimal("0.00"))


# ---------------------------------------------------------------------------
# B. Integridad
# ---------------------------------------------------------------------------

class PresentacionVentaIntegridadTest(TestCase):
    def setUp(self):
        self.negocio = _negocio()
        self.producto = _producto(self.negocio)

    def test_factor_cero_invalido(self):
        pv = PresentacionVenta(
            negocio=self.negocio,
            producto=self.producto,
            nombre="Invalida",
            factor=Decimal("0"),
            precio=Decimal("100"),
        )
        with self.assertRaises(ValidationError):
            pv.full_clean()

    def test_factor_negativo_invalido(self):
        pv = PresentacionVenta(
            negocio=self.negocio,
            producto=self.producto,
            nombre="Invalida",
            factor=Decimal("-1"),
            precio=Decimal("100"),
        )
        with self.assertRaises(ValidationError):
            pv.full_clean()

    def test_precio_negativo_invalido(self):
        pv = PresentacionVenta(
            negocio=self.negocio,
            producto=self.producto,
            nombre="Invalida",
            factor=Decimal("1"),
            precio=Decimal("-10"),
        )
        with self.assertRaises(ValidationError):
            pv.full_clean()

    def test_nombre_unico_por_producto_negocio(self):
        _presentacion(self.negocio, self.producto, "Unidad")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PresentacionVenta.objects.all_tenants().create(
                negocio=self.negocio,
                producto=self.producto,
                nombre="Unidad",
                factor=Decimal("2"),
                precio=Decimal("200"),
            )

    def test_mismo_nombre_diferente_producto_ok(self):
        otro = _producto(self.negocio, "Medialunas")
        _presentacion(self.negocio, self.producto, "Unidad")
        pv2 = _presentacion(self.negocio, otro, "Unidad")
        self.assertIsNotNone(pv2.pk)

    def test_mismo_nombre_diferente_negocio_ok(self):
        otro_negocio = _negocio("Otro negocio")
        otro_producto = _producto(otro_negocio, "Factura")
        _presentacion(self.negocio, self.producto, "Unidad")
        pv2 = _presentacion(otro_negocio, otro_producto, "Unidad")
        self.assertIsNotNone(pv2.pk)

    def test_clean_rechaza_producto_de_otro_negocio(self):
        otro_negocio = _negocio("Negocio Ajeno")
        otro_producto = _producto(otro_negocio, "Macarrones")
        pv = PresentacionVenta(
            negocio=self.negocio,
            producto=otro_producto,
            nombre="Unidad",
            factor=Decimal("1"),
            precio=Decimal("100"),
        )
        with self.assertRaises(ValidationError):
            pv.clean()

    def test_tenant_isolation(self):
        otro_negocio = _negocio("Ajeno")
        otro_producto = _producto(otro_negocio, "Otro producto")
        _presentacion(self.negocio, self.producto, "Unidad")
        _presentacion(otro_negocio, otro_producto, "Unidad")

        from core.managers import set_current_business, clear_current_business
        try:
            set_current_business(self.negocio)
            qs = PresentacionVenta.objects.filter(negocio=self.negocio)
            self.assertEqual(qs.count(), 1)
            self.assertEqual(qs.first().negocio, self.negocio)
        finally:
            clear_current_business()


# ---------------------------------------------------------------------------
# C. Admin
# ---------------------------------------------------------------------------

class PresentacionVentaAdminTest(TestCase):
    def setUp(self):
        self.negocio = _negocio("Admin Negocio")
        self.user = _superusuario(self.negocio)
        self.producto = _producto(self.negocio)
        self.client = Client()
        self.client.force_login(self.user)

    def test_changelist_accesible(self):
        url = reverse("admin:ventas_presentacionventa_changelist")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_add_view_accesible(self):
        url = reverse("admin:ventas_presentacionventa_add")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_change_view_accesible(self):
        pv = _presentacion(self.negocio, self.producto)
        url = reverse("admin:ventas_presentacionventa_change", args=[pv.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_inline_visible_en_producto(self):
        url = reverse("admin:stock_producto_change", args=[self.producto.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Presentaciones de venta")

    def test_change_view_presentacion_ajena_redirige(self):
        otro_negocio = _negocio("Negocio Ajeno Admin")
        otro_producto = _producto(otro_negocio, "Producto Ajeno")
        pv = _presentacion(otro_negocio, otro_producto, "Unidad")
        url = reverse("admin:ventas_presentacionventa_change", args=[pv.pk])
        resp = self.client.get(url)
        self.assertIn(resp.status_code, [302, 403])


# ---------------------------------------------------------------------------
# D. Compatibilidad con POS
# ---------------------------------------------------------------------------

class PresentacionVentaCompatibilidadPOSTest(TestCase):
    def setUp(self):
        self.negocio = _negocio("POS Negocio")
        self.producto = _producto(self.negocio)

    def test_presentacion_no_afecta_campo_presentacion_de_producto(self):
        self.producto.presentacion = "texto libre legado"
        self.producto.save(update_fields=["presentacion"])
        _presentacion(self.negocio, self.producto, "Unidad")
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.presentacion, "texto libre legado")

    def test_producto_venta_activo_tiene_precio_venta_independiente(self):
        pv = _presentacion(self.negocio, self.producto, "Unidad", "1.00", "999")
        self.assertNotEqual(self.producto.precio_venta, pv.precio)
        self.assertEqual(self.producto.precio_venta, Decimal("100"))

    def test_presentaciones_no_modifican_stock_actual(self):
        stock_antes = self.producto.stock_actual
        _presentacion(self.negocio, self.producto, "Unidad")
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_antes)

    def test_related_name_presentaciones(self):
        _presentacion(self.negocio, self.producto, "Unidad")
        _presentacion(self.negocio, self.producto, "Docena", "12.00", "1100")
        self.assertEqual(self.producto.presentaciones.count(), 2)

    def test_ordering_por_factor(self):
        _presentacion(self.negocio, self.producto, "Docena", "12.00", "1100")
        _presentacion(self.negocio, self.producto, "Unidad", "1.00", "100")
        _presentacion(self.negocio, self.producto, "Media docena", "6.00", "550")
        factores = list(
            PresentacionVenta.objects.all_tenants()
            .filter(producto=self.producto)
            .values_list("factor", flat=True)
        )
        self.assertEqual(factores, [Decimal("1.00"), Decimal("6.00"), Decimal("12.00")])
