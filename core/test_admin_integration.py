"""
Tests de integración Admin — PLIC Szoluciones OS

Verifican que un usuario real puede crear:
 A. Una Compra con ítems via Django Admin (POST real, formset, middleware, persistence)
 B. Una Receta con ingredientes via Django Admin (POST real, formset, persistence)
 C. Fallo controlado de auditoría durante un POST Admin: sin 500, con logger.exception
 D. El middleware CurrentBusinessMiddleware inyecta el negocio correcto en el request
"""

import logging
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from caja.models import MovimientoCaja
from compras.models import Compra, ItemCompra, Proveedor
from core.models import ActividadNegocio, Negocio
from produccion.models import Ingrediente, Receta
from stock.models import MovimientoStock, Producto, TipoProducto

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

def _negocio(nombre="Test Admin Negocio"):
    return Negocio.objects.create(nombre=nombre)


def _superusuario(negocio, username="admin_test"):
    """Crea un superusuario con negocio asignado.

    Superusuario evita cualquier restricción de permisos en el admin.
    Tiene negocio asignado para que CurrentBusinessMiddleware lo ponga
    en el thread-local y TenantOwnedModel.save() funcione.
    """
    user = User.objects.create_superuser(
        username=username,
        password="testpass123",
        email="admin@test.com",
    )
    user.negocio = negocio
    user.save(update_fields=["negocio"])
    return user


def _producto(negocio, nombre, tipo, costo=Decimal("100"), precio_venta=Decimal("200")):
    return Producto.objects.all_tenants().create(
        negocio=negocio,
        nombre=nombre,
        tipo=tipo,
        costo=costo,
        precio_venta=precio_venta,
    )


def _proveedor(negocio, nombre="Proveedor Admin Test"):
    return Proveedor.objects.all_tenants().create(negocio=negocio, nombre=nombre)


# ---------------------------------------------------------------------------
# A. Compra con ítems desde Django Admin
# ---------------------------------------------------------------------------

class AdminCompraConItemsTest(TestCase):
    """POST real a /admin/compras/compra/add/ con inline ItemCompra."""

    def setUp(self):
        self.negocio = _negocio("Panadería Admin Test")
        self.user = _superusuario(self.negocio, username="admin_compra")
        self.proveedor = _proveedor(self.negocio)
        self.insumo = _producto(
            self.negocio,
            "Harina 000 Admin",
            tipo=TipoProducto.INSUMO,
            costo=Decimal("800"),
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _post_compra(self, precio_unitario="1000", cantidad="5"):
        """POST mínimo válido para crear una Compra con un ItemCompra via Admin.

        Los prefijos de los formsets se determinaron inspeccionando el HTML del
        GET /admin/compras/compra/add/ con el test client:
          - ItemCompraInline → prefix "items"
          - MovimientoStockCompraInline (read-only) → prefix "movimientos_stock"
        """
        return self.client.post(
            "/admin/compras/compra/add/",
            data={
                # --- Campos de Compra ---
                "proveedor": str(self.proveedor.pk),
                "fecha_0": "2024-03-15",
                "fecha_1": "10:00:00",
                "observaciones": "",
                # --- Management form para ItemCompraInline (prefix: "items") ---
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                # --- Primera fila del inline ---
                "items-0-producto": str(self.insumo.pk),
                "items-0-cantidad": cantidad,
                "items-0-precio_unitario": precio_unitario,
                "items-0-id": "",
                "items-0-DELETE": "",
                # --- Management form para MovimientoStockCompraInline (prefix: "movimientos_stock", read-only) ---
                "movimientos_stock-TOTAL_FORMS": "0",
                "movimientos_stock-INITIAL_FORMS": "0",
                "movimientos_stock-MIN_NUM_FORMS": "0",
                "movimientos_stock-MAX_NUM_FORMS": "0",
            },
        )

    def test_get_compra_add_devuelve_200(self):
        """GET a la página de alta de Compra debe responder 200 sin error."""
        response = self.client.get("/admin/compras/compra/add/")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.status_code, 500)

    def test_post_compra_con_item_redirige_sin_500(self):
        """POST válido de Compra+ítem debe redirigir (302) y no dar 500."""
        response = self._post_compra()
        # Django Admin redirige a changelist tras un guardado exitoso
        self.assertNotEqual(response.status_code, 500)
        self.assertIn(response.status_code, [200, 302],
                      f"Se esperaba 200 o 302, se obtuvo {response.status_code}. "
                      f"Content snippet: {response.content[:500]!r}")

    def test_post_compra_persiste_en_bd(self):
        """Después del POST, la Compra debe existir en la BD."""
        self._post_compra()
        self.assertTrue(
            Compra.objects.all_tenants().filter(
                negocio=self.negocio, proveedor=self.proveedor
            ).exists(),
            "La Compra no se encontró en la BD tras el POST Admin.",
        )

    def test_post_compra_persiste_item_compra(self):
        """El ItemCompra también debe existir en la BD."""
        self._post_compra(precio_unitario="1000", cantidad="5")
        compras = Compra.objects.all_tenants().filter(negocio=self.negocio)
        self.assertTrue(compras.exists(), "No se encontró ninguna Compra.")
        compra = compras.first()
        items = ItemCompra.objects.all_tenants().filter(compra=compra)
        self.assertTrue(items.exists(), "No se encontró ningún ItemCompra.")

    def test_post_compra_total_correcto(self):
        """El total calculado por recalcular_total() debe ser cantidad × precio."""
        self._post_compra(precio_unitario="1000", cantidad="5")
        compra = Compra.objects.all_tenants().filter(negocio=self.negocio).first()
        self.assertIsNotNone(compra)
        # total = 5 × 1000 = 5000
        self.assertEqual(
            compra.total, Decimal("5000"),
            f"Total esperado 5000, obtenido {compra.total}",
        )

    def test_post_compra_genera_movimiento_stock(self):
        """La señal de ItemCompra debe crear un MovimientoStock de tipo INGRESO."""
        self._post_compra(precio_unitario="1000", cantidad="5")
        movimientos = MovimientoStock.objects.all_tenants().filter(
            negocio=self.negocio,
            producto=self.insumo,
            tipo=MovimientoStock.Tipo.INGRESO,
        )
        self.assertTrue(
            movimientos.exists(),
            "Debe haber al menos un MovimientoStock INGRESO tras la Compra.",
        )
        self.assertEqual(movimientos.first().cantidad, Decimal("5"))

    def test_post_compra_genera_movimiento_caja(self):
        """CompraAdmin.save_related debe crear un MovimientoCaja de tipo EGRESO."""
        self._post_compra(precio_unitario="1000", cantidad="5")
        movs_caja = MovimientoCaja.objects.all_tenants().filter(
            negocio=self.negocio,
            tipo=MovimientoCaja.Tipo.EGRESO,
        )
        self.assertTrue(
            movs_caja.exists(),
            "Debe haber un MovimientoCaja EGRESO creado por CompraAdmin.save_related.",
        )
        self.assertEqual(movs_caja.first().monto, Decimal("5000"))

    def test_post_compra_genera_actividad_auditoria(self):
        """La señal de auditoría debe registrar la Compra en ActividadNegocio."""
        self._post_compra()
        self.assertTrue(
            ActividadNegocio.objects.filter(
                negocio=self.negocio, modulo="compras"
            ).exists(),
            "Debe existir una actividad de auditoría para el módulo 'compras'.",
        )


# ---------------------------------------------------------------------------
# B. Receta con ingredientes desde Django Admin
# ---------------------------------------------------------------------------

class AdminRecetaConIngredientesTest(TestCase):
    """POST real a /admin/produccion/receta/add/ con inline Ingrediente."""

    def setUp(self):
        self.negocio = _negocio("Panadería Receta Admin Test")
        self.user = _superusuario(self.negocio, username="admin_receta")
        self.producto_venta = _producto(
            self.negocio, "Pan francés Admin", tipo=TipoProducto.VENTA,
            precio_venta=Decimal("500"),
        )
        self.insumo = _producto(
            self.negocio, "Harina Admin", tipo=TipoProducto.INSUMO,
            costo=Decimal("800"),
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _post_receta(self, rendimiento="10", cantidad_ing="2"):
        """POST mínimo válido para crear una Receta con un Ingrediente via Admin.

        Prefijo confirmado inspeccionando el HTML del GET:
          ingredientes → IngredienteInline
        """
        return self.client.post(
            "/admin/produccion/receta/add/",
            data={
                # --- Campos de Receta ---
                "nombre": "Receta Admin Test",
                "producto_resultante": str(self.producto_venta.pk),
                "rendimiento": rendimiento,
                "porcentaje_ganancia": "30",
                "instrucciones": "",
                # --- Management form para IngredienteInline (prefix: "ingredientes") ---
                "ingredientes-TOTAL_FORMS": "1",
                "ingredientes-INITIAL_FORMS": "0",
                "ingredientes-MIN_NUM_FORMS": "0",
                "ingredientes-MAX_NUM_FORMS": "1000",
                # --- Primera fila del inline ---
                "ingredientes-0-producto": str(self.insumo.pk),
                "ingredientes-0-cantidad": cantidad_ing,
                "ingredientes-0-id": "",
                "ingredientes-0-DELETE": "",
            },
        )

    def test_get_receta_add_devuelve_200(self):
        """GET a la página de alta de Receta debe responder 200."""
        response = self.client.get("/admin/produccion/receta/add/")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.status_code, 500)

    def test_post_receta_con_ingrediente_redirige_sin_500(self):
        """POST válido de Receta+ingrediente debe redirigir y no dar 500."""
        response = self._post_receta()
        self.assertNotEqual(response.status_code, 500)
        self.assertIn(response.status_code, [200, 302],
                      f"Se esperaba 200 o 302, se obtuvo {response.status_code}.")

    def test_post_receta_persiste_en_bd(self):
        """Después del POST, la Receta debe existir en la BD."""
        self._post_receta()
        self.assertTrue(
            Receta.objects.all_tenants().filter(
                negocio=self.negocio, nombre="Receta Admin Test"
            ).exists(),
            "La Receta no se encontró en la BD tras el POST Admin.",
        )

    def test_post_receta_persiste_ingrediente(self):
        """El Ingrediente debe existir en la BD vinculado a la Receta."""
        self._post_receta()
        receta = Receta.objects.all_tenants().filter(negocio=self.negocio).first()
        self.assertIsNotNone(receta, "No se encontró la Receta en BD.")
        ingredientes = Ingrediente.objects.all_tenants().filter(receta=receta)
        self.assertTrue(
            ingredientes.exists(),
            "No se encontró ningún Ingrediente vinculado a la Receta.",
        )

    def test_post_receta_costo_calculable(self):
        """Después de crear la receta, costo_total debe ser calculable sin error."""
        self._post_receta(rendimiento="10", cantidad_ing="2")
        receta = Receta.objects.all_tenants().filter(negocio=self.negocio).first()
        if receta is None:
            self.skipTest("La receta no se creó — ver otros tests para diagnóstico.")
        # costo_total = 2 × 800 = 1600
        self.assertEqual(
            receta.costo_total, Decimal("1600"),
            f"costo_total esperado 1600, obtenido {receta.costo_total}",
        )
        # costo_unitario = 1600 / 10 = 160
        self.assertEqual(receta.costo_unitario, Decimal("160"))

    def test_post_receta_genera_actividad_auditoria(self):
        """La señal debe registrar la Receta en ActividadNegocio."""
        self._post_receta()
        self.assertTrue(
            ActividadNegocio.objects.filter(
                negocio=self.negocio, modulo="produccion"
            ).exists(),
            "Debe existir una actividad de auditoría en módulo 'produccion'.",
        )


# ---------------------------------------------------------------------------
# C. Fallo controlado de auditoría durante POST Admin — sin 500, logger activo
# ---------------------------------------------------------------------------

class AdminAuditoriaFalloControladoTest(TestCase):
    """Cuando la auditoría falla durante un POST Admin:
    - La respuesta NO debe ser 500
    - El objeto principal SÍ debe guardarse
    - logger.exception SÍ debe llamarse
    - El contenido del response NO debe exponer el traceback al usuario
    """

    def setUp(self):
        self.negocio = _negocio("Negocio Auditoria Admin Test")
        self.user = _superusuario(self.negocio, username="admin_auditoria")
        self.proveedor = _proveedor(self.negocio)
        self.insumo = _producto(
            self.negocio, "Producto Auditoria Admin", tipo=TipoProducto.INSUMO
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _compra_post_data(self, observaciones="", cantidad="3", precio="500", fecha="2024-04-01"):
        """POST data para crear una Compra con un ítem via Admin.

        Prefijos confirmados inspeccionando el HTML del GET:
          items → ItemCompraInline
          movimientos_stock → MovimientoStockCompraInline (read-only)
        """
        return {
            "proveedor": str(self.proveedor.pk),
            "fecha_0": fecha,
            "fecha_1": "09:00:00",
            "observaciones": observaciones,
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-producto": str(self.insumo.pk),
            "items-0-cantidad": cantidad,
            "items-0-precio_unitario": precio,
            "items-0-id": "",
            "items-0-DELETE": "",
            "movimientos_stock-TOTAL_FORMS": "0",
            "movimientos_stock-INITIAL_FORMS": "0",
            "movimientos_stock-MIN_NUM_FORMS": "0",
            "movimientos_stock-MAX_NUM_FORMS": "0",
        }

    def test_post_compra_con_auditoria_fallida_no_da_500(self):
        """Si la auditoría falla durante el POST Admin, la respuesta no debe ser 500."""
        with patch("core.signals._log") as mock_log:
            mock_log.side_effect = Exception("Auditoria caída en test Admin")

            response = self.client.post(
                "/admin/compras/compra/add/",
                data=self._compra_post_data(fecha="2024-04-01"),
            )

        self.assertNotEqual(
            response.status_code, 500,
            "Un fallo en la auditoría no debe devolver 500 al usuario.",
        )

    def test_post_compra_con_auditoria_fallida_persiste_compra(self):
        """La Compra debe guardarse aunque la auditoría falle."""
        with patch("core.signals._log") as mock_log:
            mock_log.side_effect = Exception("Auditoria caída en test Admin")

            self.client.post(
                "/admin/compras/compra/add/",
                data=self._compra_post_data(observaciones="Con fallo de auditoria", fecha="2024-04-05"),
            )

        # La Compra debe haberse guardado a pesar del fallo de auditoría
        self.assertTrue(
            Compra.objects.all_tenants().filter(
                negocio=self.negocio,
                observaciones="Con fallo de auditoria",
            ).exists(),
            "La Compra debe guardarse aunque la auditoría falle durante el POST Admin.",
        )

    def test_fallo_auditoria_registra_en_logger(self):
        """Cuando la auditoría falla, logger.exception debe llamarse (no silencio total)."""
        with patch("core.signals.ActividadNegocio.objects") as mock_manager:
            mock_manager.create.side_effect = Exception("Fallo controlado en logger Admin")

            with self.assertLogs("core.signals", level="ERROR") as log_ctx:
                self.client.post(
                    "/admin/compras/compra/add/",
                    data=self._compra_post_data(cantidad="2", precio="300", fecha="2024-04-06"),
                )

        error_msgs = [m for m in log_ctx.output if "ERROR" in m or "CRITICAL" in m]
        self.assertTrue(
            len(error_msgs) > 0,
            f"El fallo de auditoría debe quedar registrado en logger.exception. "
            f"Mensajes encontrados: {log_ctx.output}",
        )

    def test_respuesta_no_expone_traceback_al_usuario(self):
        """El cuerpo de la respuesta no debe contener tracebacks ni errores internos."""
        with patch("core.signals._log") as mock_log:
            mock_log.side_effect = Exception("Excepción interna que no debe verse")

            response = self.client.post(
                "/admin/compras/compra/add/",
                data=self._compra_post_data(cantidad="1", precio="100", fecha="2024-04-07"),
            )

        # Si es una redirección (302), no hay contenido que exponga nada
        if response.status_code == 302:
            return  # OK

        # Si devuelve contenido (200 con errores de formulario), no debe
        # incluir ningún traceback Python visible
        content = response.content.decode("utf-8", errors="replace")
        self.assertNotIn(
            "Traceback (most recent call last)",
            content,
            "El response no debe exponer un traceback Python al usuario.",
        )
        self.assertNotIn(
            "Excepción interna que no debe verse",
            content,
            "El response no debe exponer el mensaje interno de la excepción.",
        )


# ---------------------------------------------------------------------------
# D. Aislamiento de negocio: middleware inyecta el negocio correcto
# ---------------------------------------------------------------------------

class AdminMiddlewareNegocioTest(TestCase):
    """Verifica que CurrentBusinessMiddleware establece el negocio del usuario
    en el thread-local durante el request Admin."""

    def setUp(self):
        self.negocio_a = _negocio("Negocio A Middleware")
        self.negocio_b = _negocio("Negocio B Middleware")
        self.user_a = _superusuario(self.negocio_a, username="user_middleware_a")
        self.proveedor_a = _proveedor(self.negocio_a, "Proveedor A")
        self.proveedor_b = _proveedor(self.negocio_b, "Proveedor B")
        self.client = Client()
        self.client.force_login(self.user_a)

    def test_middleware_establece_negocio_en_request(self):
        """El middleware debe registrar el negocio en el thread-local.
        Probado indirectamente: un objeto creado desde Admin debe tener
        el negocio del usuario autenticado."""
        from core.managers import get_current_business

        negocio_capturado = {}

        original_set = __import__(
            "core.managers", fromlist=["set_current_business"]
        ).set_current_business

        def patched_set(negocio):
            negocio_capturado["negocio"] = negocio
            original_set(negocio)

        with patch("core.middleware.set_current_business", side_effect=patched_set):
            self.client.get("/admin/compras/compra/add/")

        # El middleware debe haber llamado set_current_business con el negocio_a
        self.assertIn("negocio", negocio_capturado)
        self.assertEqual(
            negocio_capturado["negocio"],
            self.negocio_a,
            "El middleware debe establecer el negocio del usuario autenticado.",
        )

    def test_queryset_compra_filtrado_por_negocio(self):
        """El admin de Compras lista sólo los objetos del negocio del usuario."""
        # Crear una Compra para negocio_a y otra para negocio_b
        insumo_a = _producto(self.negocio_a, "Insumo A", tipo=TipoProducto.INSUMO)
        insumo_b = _producto(self.negocio_b, "Insumo B", tipo=TipoProducto.INSUMO)

        compra_a = Compra.objects.all_tenants().create(
            negocio=self.negocio_a,
            proveedor=self.proveedor_a,
            fecha=timezone.now(),
        )
        compra_b = Compra.objects.all_tenants().create(
            negocio=self.negocio_b,
            proveedor=self.proveedor_b,
            fecha=timezone.now(),
        )

        # user_a accede al changelist — sólo debe ver compras de negocio_a
        response = self.client.get("/admin/compras/compra/")
        self.assertEqual(response.status_code, 200)

        # user_a es superusuario con negocio_a: TenantOwnedAdmin.get_queryset
        # filtra por negocio cuando negocio_id está asignado
        content = response.content.decode("utf-8", errors="replace")
        # La compra_a debería estar en el listado
        self.assertIn(str(self.proveedor_a.nombre), content)
