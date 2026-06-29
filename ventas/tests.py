from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from core.models import Negocio
from stock.models import MovimientoStock, Producto, TipoProducto

from .models import ItemVenta, PresentacionVenta, Venta

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


# ===========================================================================
# ETAPA 2 — Presentaciones en ventas y stock
# ===========================================================================

def _venta(negocio):
    return Venta.objects.all_tenants().create(
        negocio=negocio,
        metodo_pago="EFECTIVO",
    )


def _item_venta(negocio, venta, producto, cantidad, precio_unitario=None, presentacion=None):
    kwargs = dict(
        negocio=negocio,
        venta=venta,
        producto=producto,
        cantidad=Decimal(str(cantidad)),
    )
    if precio_unitario is not None:
        kwargs["precio_unitario"] = Decimal(str(precio_unitario))
    else:
        kwargs["precio_unitario"] = Decimal("0")
    if presentacion is not None:
        kwargs["presentacion"] = presentacion
    return ItemVenta.objects.all_tenants().create(**kwargs)


# ---------------------------------------------------------------------------
# A. Compatibilidad
# ---------------------------------------------------------------------------

class VentaCompatibilidadTest(TestCase):
    """Sin presentación: comportamiento igual que antes de Etapa 2."""

    def setUp(self):
        self.negocio = _negocio("Compat Test")
        self.producto = _producto(self.negocio)
        self.venta = _venta(self.negocio)

    def test_venta_sin_presentacion_usa_precio_producto(self):
        item = _item_venta(self.negocio, self.venta, self.producto, "1")
        self.assertEqual(item.precio_unitario, self.producto.precio_venta)

    def test_venta_sin_presentacion_descuenta_cantidad_exacta(self):
        stock_antes = self.producto.stock_actual
        _item_venta(self.negocio, self.venta, self.producto, "3")
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_antes - Decimal("3"))

    def test_venta_sin_presentacion_crea_un_movimiento_egreso(self):
        _item_venta(self.negocio, self.venta, self.producto, "2")
        movs = MovimientoStock.objects.all_tenants().filter(
            negocio=self.negocio,
            producto=self.producto,
            tipo=MovimientoStock.Tipo.EGRESO,
        )
        self.assertEqual(movs.count(), 1)
        self.assertEqual(movs.first().cantidad, Decimal("2"))

    def test_venta_historica_presentacion_null_accesible(self):
        item = _item_venta(self.negocio, self.venta, self.producto, "1", precio_unitario="100")
        self.assertIsNone(item.presentacion)
        item.refresh_from_db()
        self.assertIsNone(item.presentacion)
        self.assertEqual(item.cantidad, Decimal("1"))


# ---------------------------------------------------------------------------
# B. Venta con presentación y factor
# ---------------------------------------------------------------------------

class VentaConPresentacionTest(TestCase):
    """Con presentación: stock = cantidad × factor; precio = presentacion.precio."""

    def setUp(self):
        self.negocio = _negocio("Factor Test")
        self.producto = _producto(self.negocio)
        self.venta = _venta(self.negocio)
        self.media_docena = _presentacion(
            self.negocio, self.producto, "Media docena", factor="6.00", precio="4000.00"
        )

    def test_precio_unitario_tomado_de_presentacion(self):
        item = _item_venta(self.negocio, self.venta, self.producto, "1",
                           presentacion=self.media_docena)
        self.assertEqual(item.precio_unitario, Decimal("4000.00"))

    def test_movimiento_stock_descuenta_factor(self):
        stock_antes = self.producto.stock_actual
        _item_venta(self.negocio, self.venta, self.producto, "1",
                    presentacion=self.media_docena)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_antes - Decimal("6"))

    def test_movimiento_egreso_cantidad_es_factor(self):
        _item_venta(self.negocio, self.venta, self.producto, "1",
                    presentacion=self.media_docena)
        mov = MovimientoStock.objects.all_tenants().filter(
            negocio=self.negocio,
            producto=self.producto,
            tipo=MovimientoStock.Tipo.EGRESO,
        ).first()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.cantidad, Decimal("6"))

    def test_total_venta_con_presentacion(self):
        self.venta.items.all().delete()
        item = _item_venta(self.negocio, self.venta, self.producto, "1",
                           presentacion=self.media_docena)
        self.venta.recalcular_total()
        self.assertEqual(self.venta.total, Decimal("4000.00"))


# ---------------------------------------------------------------------------
# C. Multiplicación (cantidad > 1 con factor)
# ---------------------------------------------------------------------------

class VentaMultiplicacionTest(TestCase):
    """Dos unidades de una presentación con factor 6 → egreso 12."""

    def setUp(self):
        self.negocio = _negocio("Multi Test")
        self.producto = _producto(self.negocio)
        self.venta = _venta(self.negocio)
        self.media_docena = _presentacion(
            self.negocio, self.producto, "Media docena", factor="6.00", precio="4000.00"
        )

    def test_dos_unidades_factor_6_descuenta_12(self):
        stock_antes = self.producto.stock_actual
        _item_venta(self.negocio, self.venta, self.producto, "2",
                    presentacion=self.media_docena)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_antes - Decimal("12"))

    def test_movimiento_egreso_es_cantidad_por_factor(self):
        _item_venta(self.negocio, self.venta, self.producto, "2",
                    presentacion=self.media_docena)
        mov = MovimientoStock.objects.all_tenants().filter(
            negocio=self.negocio,
            producto=self.producto,
            tipo=MovimientoStock.Tipo.EGRESO,
        ).first()
        self.assertEqual(mov.cantidad, Decimal("12"))

    def test_total_dos_unidades_presentacion(self):
        _item_venta(self.negocio, self.venta, self.producto, "2",
                    presentacion=self.media_docena)
        self.venta.recalcular_total()
        self.assertEqual(self.venta.total, Decimal("8000.00"))


# ---------------------------------------------------------------------------
# D. Integridad
# ---------------------------------------------------------------------------

class ItemVentaIntegridadTest(TestCase):
    def setUp(self):
        self.negocio = _negocio("Integridad Test")
        self.producto = _producto(self.negocio)
        self.venta = _venta(self.negocio)
        self.presentacion = _presentacion(self.negocio, self.producto, "Unidad", "1.00", "100")

    def test_presentacion_otro_producto_rechazada(self):
        otro_producto = _producto(self.negocio, "Otro producto")
        pv_otro = _presentacion(self.negocio, otro_producto, "Unidad", "1.00", "100")
        item = ItemVenta(
            negocio=self.negocio,
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100"),
            presentacion=pv_otro,
        )
        with self.assertRaises(ValidationError):
            item.clean()

    def test_presentacion_otro_negocio_rechazada(self):
        otro_negocio = _negocio("Negocio Ajeno")
        otro_producto = _producto(otro_negocio, "Producto Ajeno")
        pv_ajena = _presentacion(otro_negocio, otro_producto, "Unidad", "1.00", "100")
        item = ItemVenta(
            negocio=self.negocio,
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100"),
            presentacion=pv_ajena,
        )
        with self.assertRaises(ValidationError):
            item.clean()

    def test_presentacion_inactiva_rechazada_nueva_venta(self):
        pv_inactiva = PresentacionVenta.objects.all_tenants().create(
            negocio=self.negocio,
            producto=self.producto,
            nombre="Inactiva",
            factor=Decimal("1"),
            precio=Decimal("100"),
            activo=False,
        )
        item = ItemVenta(
            negocio=self.negocio,
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100"),
            presentacion=pv_inactiva,
        )
        with self.assertRaises(ValidationError):
            item.clean()

    def test_presentacion_inactiva_existente_no_rechazada_en_edicion(self):
        """Un ítem existente puede mantener una presentación inactiva al editar."""
        pv = PresentacionVenta.objects.all_tenants().create(
            negocio=self.negocio,
            producto=self.producto,
            nombre="Activa temporalmente",
            factor=Decimal("1"),
            precio=Decimal("100"),
            activo=True,
        )
        item = _item_venta(self.negocio, self.venta, self.producto, "1",
                           presentacion=pv)
        pv.activo = False
        pv.save(update_fields=["activo"])
        item_existente = ItemVenta(
            pk=item.pk,
            negocio=self.negocio,
            venta=self.venta,
            producto=self.producto,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("100"),
            presentacion=pv,
        )
        # No debe lanzar error porque self.pk está seteado (es una edición)
        item_existente.clean()


# ---------------------------------------------------------------------------
# E. Edición — comportamiento real documentado
# ---------------------------------------------------------------------------

class VentaEdicionTest(TestCase):
    """
    LIMITACIÓN CONOCIDA: Editar la cantidad de un ItemVenta existente NO actualiza
    el stock. La señal itemventa_post_save sólo actúa sobre created=True. Este es
    el comportamiento existente del proyecto antes y después de la Etapa 2.

    Lo que sí se garantiza: editar no DUPLICA movimientos.
    """

    def setUp(self):
        self.negocio = _negocio("Edicion Test")
        self.producto = _producto(self.negocio)
        self.venta = _venta(self.negocio)
        self.presentacion = _presentacion(
            self.negocio, self.producto, "Media docena", factor="6.00", precio="4000.00"
        )

    def test_edicion_no_duplica_movimiento_stock(self):
        """Modificar cantidad de un ItemVenta existente no crea nuevos movimientos."""
        item = _item_venta(self.negocio, self.venta, self.producto, "1",
                           presentacion=self.presentacion)
        count_antes = MovimientoStock.objects.all_tenants().filter(
            negocio=self.negocio, producto=self.producto
        ).count()
        item.cantidad = Decimal("3")
        item.save()
        count_despues = MovimientoStock.objects.all_tenants().filter(
            negocio=self.negocio, producto=self.producto
        ).count()
        self.assertEqual(count_antes, count_despues,
                         "Editar un ItemVenta no debe crear movimientos adicionales.")

    def test_creacion_crea_exactamente_un_movimiento(self):
        """Un solo movimiento EGRESO con cantidad = 1 × 6 = 6."""
        _item_venta(self.negocio, self.venta, self.producto, "1",
                    presentacion=self.presentacion)
        movs = MovimientoStock.objects.all_tenants().filter(
            negocio=self.negocio,
            producto=self.producto,
            tipo=MovimientoStock.Tipo.EGRESO,
        )
        self.assertEqual(movs.count(), 1)
        self.assertEqual(movs.first().cantidad, Decimal("6"))

    def test_borrado_item_crea_reversa_con_factor(self):
        """Borrar un ItemVenta con presentación crea un INGRESO de reversa × factor."""
        stock_antes = self.producto.stock_actual
        item = _item_venta(self.negocio, self.venta, self.producto, "1",
                           presentacion=self.presentacion)
        self.producto.refresh_from_db()
        stock_tras_venta = self.producto.stock_actual
        self.assertEqual(stock_tras_venta, stock_antes - Decimal("6"))

        item.delete()
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock_actual, stock_antes,
                         "Borrar el ítem debe restaurar el stock al valor original.")


# ---------------------------------------------------------------------------
# F. Aislamiento por negocio en Admin
# ---------------------------------------------------------------------------

class VentaAdminAislamientoTest(TestCase):
    def setUp(self):
        self.negocio_a = _negocio("Negocio A Venta")
        self.negocio_b = _negocio("Negocio B Venta")
        self.user_a = _superusuario(self.negocio_a, username="admin_venta_a")
        self.producto_b = _producto(self.negocio_b, "Producto B")
        self.venta_b = _venta(self.negocio_b)
        self.client = Client()
        self.client.force_login(self.user_a)

    def test_change_view_venta_negocio_ajeno_no_devuelve_200(self):
        url = reverse("admin:ventas_venta_change", args=[self.venta_b.pk])
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200,
                            "El change view de una Venta de otro negocio no debe devolver 200.")

    def test_admin_venta_create_crea_movimiento_caja(self):
        """Crear una Venta via Admin genera el MovimientoCaja (bug fix: save_related estaba mal)."""
        producto_a = _producto(self.negocio_a, "Producto A Venta Admin")
        response = self.client.post(
            "/admin/ventas/venta/add/",
            data={
                "fecha_0": "2024-06-01",
                "fecha_1": "10:00:00",
                "metodo_pago": "EFECTIVO",
                "observaciones": "",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-producto": str(producto_a.pk),
                "items-0-presentacion": "",
                "items-0-cantidad": "2",
                "items-0-precio_unitario": "500",
                "items-0-id": "",
                "items-0-DELETE": "",
                "movimientos_stock-TOTAL_FORMS": "0",
                "movimientos_stock-INITIAL_FORMS": "0",
                "movimientos_stock-MIN_NUM_FORMS": "0",
                "movimientos_stock-MAX_NUM_FORMS": "0",
            },
        )
        self.assertEqual(
            response.status_code, 302,
            f"POST a /admin/ventas/venta/add/ debe retornar 302 (guardado OK). "
            f"Se obtuvo {response.status_code}. Content: {response.content[:600]!r}",
        )
        from caja.models import MovimientoCaja
        self.assertTrue(
            MovimientoCaja.objects.all_tenants().filter(
                negocio=self.negocio_a,
                tipo=MovimientoCaja.Tipo.INGRESO,
            ).exists(),
            "Crear Venta via Admin debe generar MovimientoCaja de INGRESO.",
        )
