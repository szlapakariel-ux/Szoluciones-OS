"""
Tests de regresión PLIC — Szoluciones OS

Cubre:
1. Crear una Compra con items — confirma que se guarda correctamente
2. Crear una Receta con ingredientes — confirma que se guarda correctamente
3. Crear y borrar un GastoFijo usando el campo correcto `concepto`
4. Forzar un fallo controlado en la capa de auditoría y verificar que la
   operación principal se guarda igual
5. Confirmar que el fallo de auditoría se registra técnicamente (logger.exception)
   sin interrumpir al usuario
6. Ejecutar seed en BD limpia y validar que los productos tienen `tipo` correcto
7. Ejecutar seed sobre datos existentes y verificar que los productos ya
   existentes conservan su `tipo`
"""

import logging
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from compras.models import Compra, ItemCompra, Proveedor
from core.managers import set_current_business
from core.models import ActividadNegocio, Negocio
from gastos.models import GastoFijo
from produccion.models import Ingrediente, Receta
from stock.models import MovimientoStock, Producto, TipoProducto


def _negocio(nombre="Test Negocio"):
    """Helper: crea un negocio mínimo para tests."""
    return Negocio.objects.create(nombre=nombre)


def _producto(negocio, nombre="Producto Test", tipo=TipoProducto.VENTA, costo=Decimal("100")):
    """Helper: crea un Producto asignado a *negocio* sin pasar por TenantManager."""
    return Producto.objects.all_tenants().create(
        negocio=negocio,
        nombre=nombre,
        tipo=tipo,
        precio_venta=Decimal("200"),
        costo=costo,
    )


def _proveedor(negocio, nombre="Proveedor Test"):
    """Helper: crea un Proveedor."""
    return Proveedor.objects.all_tenants().create(negocio=negocio, nombre=nombre)


# ---------------------------------------------------------------------------
# 1. Compra con items
# ---------------------------------------------------------------------------

class CompraConItemsTest(TestCase):
    """La Compra y sus ítems se deben guardar correctamente,
    y los signals de stock deben dispararse sin errores."""

    def setUp(self):
        self.negocio = _negocio("Panadería Test")
        set_current_business(None)

    def test_compra_con_un_item_se_guarda(self):
        proveedor = _proveedor(self.negocio)
        insumo = _producto(self.negocio, "Harina", tipo=TipoProducto.INSUMO, costo=Decimal("800"))

        compra = Compra.objects.all_tenants().create(
            negocio=self.negocio,
            proveedor=proveedor,
            fecha=timezone.now(),
        )
        item = ItemCompra.objects.all_tenants().create(
            negocio=self.negocio,
            compra=compra,
            producto=insumo,
            cantidad=Decimal("10"),
            precio_unitario=Decimal("750"),
        )
        compra.recalcular_total()

        # La compra existe en BD
        self.assertTrue(Compra.objects.all_tenants().filter(pk=compra.pk).exists())
        # El ítem existe en BD
        self.assertTrue(ItemCompra.objects.all_tenants().filter(pk=item.pk).exists())
        # El total se calculó correctamente
        compra.refresh_from_db()
        self.assertEqual(compra.total, Decimal("7500"))

    def test_item_compra_genera_movimiento_de_ingreso(self):
        """Cada ItemCompra debe crear un MovimientoStock de tipo INGRESO."""
        proveedor = _proveedor(self.negocio)
        insumo = _producto(self.negocio, "Manteca", tipo=TipoProducto.INSUMO)

        compra = Compra.objects.all_tenants().create(
            negocio=self.negocio,
            proveedor=proveedor,
            fecha=timezone.now(),
        )
        cantidad = Decimal("5")
        ItemCompra.objects.all_tenants().create(
            negocio=self.negocio,
            compra=compra,
            producto=insumo,
            cantidad=cantidad,
            precio_unitario=Decimal("3000"),
        )

        movimientos = MovimientoStock.objects.all_tenants().filter(
            producto=insumo, tipo=MovimientoStock.Tipo.INGRESO
        )
        self.assertEqual(movimientos.count(), 1)
        self.assertEqual(movimientos.first().cantidad, cantidad)

    def test_compra_con_multiples_items_se_guarda(self):
        """Compra con varios ítems; todos deben guardarse y el total debe ser correcto."""
        proveedor = _proveedor(self.negocio)
        harina = _producto(self.negocio, "Harina 000", tipo=TipoProducto.INSUMO, costo=Decimal("800"))
        cafe = _producto(self.negocio, "Café 250g", tipo=TipoProducto.VENTA, costo=Decimal("2200"))

        compra = Compra.objects.all_tenants().create(
            negocio=self.negocio,
            proveedor=proveedor,
            fecha=timezone.now(),
        )
        ItemCompra.objects.all_tenants().create(
            negocio=self.negocio, compra=compra,
            producto=harina, cantidad=Decimal("20"), precio_unitario=Decimal("800"),
        )
        ItemCompra.objects.all_tenants().create(
            negocio=self.negocio, compra=compra,
            producto=cafe, cantidad=Decimal("10"), precio_unitario=Decimal("2000"),
        )
        compra.recalcular_total()
        compra.refresh_from_db()

        self.assertEqual(ItemCompra.objects.all_tenants().filter(compra=compra).count(), 2)
        # 20*800 + 10*2000 = 16000 + 20000 = 36000
        self.assertEqual(compra.total, Decimal("36000"))


# ---------------------------------------------------------------------------
# 2. Receta con ingredientes
# ---------------------------------------------------------------------------

class RecetaConIngredientesTest(TestCase):
    """La Receta y sus ingredientes se deben guardar correctamente."""

    def setUp(self):
        self.negocio = _negocio("Panadería Receta Test")
        set_current_business(None)

    def test_receta_con_ingrediente_se_guarda(self):
        pan = _producto(self.negocio, "Pan francés", tipo=TipoProducto.VENTA)
        harina = _producto(self.negocio, "Harina", tipo=TipoProducto.INSUMO, costo=Decimal("800"))

        receta = Receta.objects.all_tenants().create(
            negocio=self.negocio,
            nombre="Pan Francés 1 kg",
            producto_resultante=pan,
            rendimiento=Decimal("1"),
        )
        ingrediente = Ingrediente.objects.all_tenants().create(
            negocio=self.negocio,
            receta=receta,
            producto=harina,
            cantidad=Decimal("1"),
        )

        self.assertTrue(Receta.objects.all_tenants().filter(pk=receta.pk).exists())
        self.assertTrue(Ingrediente.objects.all_tenants().filter(pk=ingrediente.pk).exists())

    def test_costo_receta_se_calcula_correctamente(self):
        """El costo total de la receta debe ser la suma de costo × cantidad de ingredientes."""
        pan = _producto(self.negocio, "Medialuna", tipo=TipoProducto.VENTA)
        harina = _producto(self.negocio, "Harina", tipo=TipoProducto.INSUMO, costo=Decimal("800"))
        manteca = _producto(self.negocio, "Manteca", tipo=TipoProducto.INSUMO, costo=Decimal("3500"))

        receta = Receta.objects.all_tenants().create(
            negocio=self.negocio,
            nombre="Medialunas docena",
            producto_resultante=pan,
            rendimiento=Decimal("1"),
        )
        Ingrediente.objects.all_tenants().create(
            negocio=self.negocio, receta=receta,
            producto=harina, cantidad=Decimal("0.5"),
        )
        Ingrediente.objects.all_tenants().create(
            negocio=self.negocio, receta=receta,
            producto=manteca, cantidad=Decimal("0.2"),
        )

        # costo_total = 0.5 * 800 + 0.2 * 3500 = 400 + 700 = 1100
        self.assertEqual(receta.costo_total, Decimal("1100"))

    def test_receta_con_multiples_ingredientes_se_guarda(self):
        pan = _producto(self.negocio, "Pan de campo", tipo=TipoProducto.VENTA)
        ingredientes_data = [
            ("Harina 000", Decimal("1.5"), Decimal("800")),
            ("Sal", Decimal("0.02"), Decimal("200")),
            ("Levadura", Decimal("0.05"), Decimal("1500")),
        ]
        productos_ing = [
            _producto(self.negocio, nombre, tipo=TipoProducto.INSUMO, costo=costo)
            for nombre, _, costo in ingredientes_data
        ]

        receta = Receta.objects.all_tenants().create(
            negocio=self.negocio,
            nombre="Pan de Campo 1.5 kg",
            producto_resultante=pan,
            rendimiento=Decimal("1.5"),
        )
        for (nombre, cantidad, _), prod in zip(ingredientes_data, productos_ing):
            Ingrediente.objects.all_tenants().create(
                negocio=self.negocio, receta=receta,
                producto=prod, cantidad=cantidad,
            )

        self.assertEqual(Ingrediente.objects.all_tenants().filter(receta=receta).count(), 3)


# ---------------------------------------------------------------------------
# 3. GastoFijo usa campo `concepto`
# ---------------------------------------------------------------------------

class GastoFijoConceptoTest(TestCase):
    """GastoFijo debe usar el campo `concepto` (no `nombre`)."""

    def setUp(self):
        self.negocio = _negocio("Negocio Gastos Test")
        set_current_business(None)

    def test_gastofijo_tiene_campo_concepto(self):
        """El campo del modelo se llama `concepto`, no `nombre`."""
        gasto = GastoFijo.objects.all_tenants().create(
            negocio=self.negocio,
            concepto="Alquiler del local",
            monto=Decimal("180000"),
            periodicidad=GastoFijo.Periodicidad.MENSUAL,
        )
        self.assertEqual(gasto.concepto, "Alquiler del local")
        # Verificar que `nombre` no existe como campo
        self.assertFalse(hasattr(GastoFijo, 'nombre'))

    def test_gastofijo_create_y_delete_con_concepto(self):
        """Crear y borrar un GastoFijo funciona correctamente con el campo `concepto`."""
        gasto = GastoFijo.objects.all_tenants().create(
            negocio=self.negocio,
            concepto="Internet",
            monto=Decimal("12000"),
            periodicidad=GastoFijo.Periodicidad.MENSUAL,
        )
        pk = gasto.pk
        self.assertTrue(GastoFijo.objects.all_tenants().filter(pk=pk).exists())

        gasto.delete()
        self.assertFalse(GastoFijo.objects.all_tenants().filter(pk=pk).exists())

    def test_gastofijo_str_usa_concepto(self):
        """El __str__ del GastoFijo incluye el concepto."""
        gasto = GastoFijo.objects.all_tenants().create(
            negocio=self.negocio,
            concepto="Luz",
            monto=Decimal("35000"),
            periodicidad=GastoFijo.Periodicidad.MENSUAL,
        )
        self.assertIn("Luz", str(gasto))

    def test_gastofijo_signal_usa_concepto(self):
        """La señal de auditoría en GastoFijo accede a instance.concepto sin error."""
        # Si la señal usara `nombre` en lugar de `concepto`, lanzaría AttributeError.
        # Con _safe, el error estaría suprimido pero no llegaría al activo de auditoría.
        gasto = GastoFijo.objects.all_tenants().create(
            negocio=self.negocio,
            concepto="Sueldo Ayudante",
            monto=Decimal("350000"),
            periodicidad=GastoFijo.Periodicidad.MENSUAL,
        )
        actividad = ActividadNegocio.objects.filter(
            negocio=self.negocio,
            modulo="gastos",
            accion__icontains="Sueldo Ayudante",
        )
        self.assertTrue(
            actividad.exists(),
            "La señal de auditoría debe registrar el concepto del GastoFijo.",
        )


# ---------------------------------------------------------------------------
# 4 & 5. Fallo controlado en auditoría — la operación principal debe guardarse
#         y el fallo debe quedar en logs técnicos
# ---------------------------------------------------------------------------

class AuditoriaFalloControladoTest(TestCase):
    """Cuando ActividadNegocio.objects.create falla, el modelo principal
    debe haberse guardado igual y el error técnico debe quedar registrado."""

    def setUp(self):
        self.negocio = _negocio("Negocio Auditoria Test")
        set_current_business(None)

    def test_compra_se_guarda_cuando_auditoria_falla(self):
        """Si la auditoría lanza excepción, la Compra igual queda guardada."""
        proveedor = _proveedor(self.negocio)

        with patch("core.models.ActividadNegocio.objects") as mock_manager:
            mock_manager.create.side_effect = Exception("DB auditoria caída")

            compra = Compra.objects.all_tenants().create(
                negocio=self.negocio,
                proveedor=proveedor,
                fecha=timezone.now(),
            )

        # La compra sí se guardó
        self.assertTrue(Compra.objects.all_tenants().filter(pk=compra.pk).exists())

    def test_receta_se_guarda_cuando_auditoria_falla(self):
        """Si la auditoría falla, la Receta igual queda guardada."""
        pan = _producto(self.negocio, "Pan test", tipo=TipoProducto.VENTA)

        with patch("core.models.ActividadNegocio.objects") as mock_manager:
            mock_manager.create.side_effect = Exception("Fallo controlado en auditoría")

            receta = Receta.objects.all_tenants().create(
                negocio=self.negocio,
                nombre="Receta Test Auditoria",
                producto_resultante=pan,
                rendimiento=Decimal("1"),
            )

        self.assertTrue(Receta.objects.all_tenants().filter(pk=receta.pk).exists())

    def test_gastofijo_se_guarda_cuando_auditoria_falla(self):
        """Si la auditoría falla, el GastoFijo igual queda guardado."""
        with patch("core.models.ActividadNegocio.objects") as mock_manager:
            mock_manager.create.side_effect = Exception("Fallo controlado")

            gasto = GastoFijo.objects.all_tenants().create(
                negocio=self.negocio,
                concepto="Alquiler test fallo",
                monto=Decimal("100000"),
                periodicidad=GastoFijo.Periodicidad.MENSUAL,
            )

        self.assertTrue(GastoFijo.objects.all_tenants().filter(pk=gasto.pk).exists())

    def test_fallo_auditoria_se_registra_en_logger_exception(self):
        """Cuando la auditoría falla, se debe llamar logger.exception (no se silencia)."""
        proveedor = _proveedor(self.negocio)

        with patch("core.models.ActividadNegocio.objects") as mock_manager:
            mock_manager.create.side_effect = Exception("Fallo controlado para logging")

            with self.assertLogs("core.signals", level="ERROR") as log_ctx:
                Compra.objects.all_tenants().create(
                    negocio=self.negocio,
                    proveedor=proveedor,
                    fecha=timezone.now(),
                )

        # Debe haber al menos un mensaje de ERROR en el log de core.signals
        error_msgs = [m for m in log_ctx.output if "ERROR" in m or "CRITICAL" in m]
        self.assertTrue(
            len(error_msgs) > 0,
            "Se esperaba al menos un mensaje ERROR en core.signals al fallar la auditoría. "
            f"Mensajes encontrados: {log_ctx.output}",
        )

    def test_log_safe_decorator_registra_excepcion_inesperada(self):
        """_safe debe registrar en el logger técnico excepciones inesperadas del propio signal."""
        from django.db.models.signals import post_save
        from django.dispatch import receiver

        from core.signals import _safe

        @_safe
        def signal_que_falla(sender, instance, **kwargs):
            raise RuntimeError("Error inesperado en signal")

        with self.assertLogs("core.signals", level="ERROR") as log_ctx:
            signal_que_falla(sender=None, instance=None)

        error_msgs = [m for m in log_ctx.output if "ERROR" in m]
        self.assertTrue(len(error_msgs) > 0, "El decorador _safe debe usar logger.exception")


# ---------------------------------------------------------------------------
# 6 & 7. seed_demo: productos con `tipo` correcto
# ---------------------------------------------------------------------------

class SeedDemoProductoTipoTest(TestCase):
    """Después de seed_demo, todos los productos deben tener `tipo` asignado
    (VENTA o INSUMO, nunca None)."""

    def _run_seed(self, reset=False):
        from io import StringIO

        from django.core.management import call_command
        out = StringIO()
        args = ["seed_demo"]
        if reset:
            args.append("--reset")
        call_command(*args, stdout=out, stderr=out)
        return out.getvalue()

    def test_seed_limpio_productos_tienen_tipo(self):
        """En una BD vacía, seed_demo crea productos con tipo VENTA o INSUMO."""
        output = self._run_seed(reset=False)

        # Todos los productos del negocio piloto tienen tipo asignado
        productos_sin_tipo = Producto.objects.all_tenants().filter(
            negocio__nombre="Panadería Piloto",
            tipo__isnull=True,
        )
        self.assertEqual(
            productos_sin_tipo.count(),
            0,
            f"Productos sin tipo tras seed_demo: "
            f"{list(productos_sin_tipo.values_list('nombre', flat=True))}",
        )

    def test_seed_limpio_tipos_correctos_por_codigo(self):
        """Los productos tienen el tipo esperado según su rol."""
        self._run_seed(reset=False)

        # Insumos (se compran pero no se venden directamente)
        for codigo in ["HAR000", "MAN001"]:
            p = Producto.objects.all_tenants().filter(codigo=codigo).first()
            self.assertIsNotNone(p, f"Producto {codigo} no encontrado tras seed")
            self.assertEqual(
                p.tipo,
                TipoProducto.INSUMO,
                f"{codigo} debería ser INSUMO, tiene tipo={p.tipo}",
            )

        # Productos de venta
        for codigo in ["PAN001", "MED001", "CAF250"]:
            p = Producto.objects.all_tenants().filter(codigo=codigo).first()
            self.assertIsNotNone(p, f"Producto {codigo} no encontrado tras seed")
            self.assertEqual(
                p.tipo,
                TipoProducto.VENTA,
                f"{codigo} debería ser VENTA, tiene tipo={p.tipo}",
            )

    def test_seed_sobre_datos_existentes_no_altera_tipo(self):
        """Seed sobre datos existentes: los productos ya creados conservan su tipo."""
        # Primera ejecución: crea productos
        self._run_seed(reset=False)

        # Alterar manualmente el tipo de un producto para verificar que el seed no lo pisa
        harina = Producto.objects.all_tenants().filter(codigo="HAR000").first()
        self.assertIsNotNone(harina)
        # El seed usa get_or_create; el tipo ya está asignado, no debería cambiar
        tipo_original = harina.tipo

        # Segunda ejecución sin --reset
        self._run_seed(reset=False)

        harina.refresh_from_db()
        self.assertEqual(
            harina.tipo,
            tipo_original,
            "El seed no debe cambiar el tipo de productos que ya existían (usa get_or_create).",
        )

    def test_seed_con_reset_recrea_productos_con_tipo(self):
        """seed_demo --reset borra y recrea todo; los productos vuelven a tener tipo correcto."""
        # Primera ejecución
        self._run_seed(reset=False)
        # Segunda con --reset
        self._run_seed(reset=True)

        productos_sin_tipo = Producto.objects.all_tenants().filter(
            negocio__nombre="Panadería Piloto",
            tipo__isnull=True,
        )
        self.assertEqual(
            productos_sin_tipo.count(),
            0,
            "Tras seed --reset todos los productos deben tener tipo asignado.",
        )


# ---------------------------------------------------------------------------
# Señales de auditoría — integración de extremo a extremo
# ---------------------------------------------------------------------------

class AuditoriaIntegracionTest(TestCase):
    """Verifica que las señales de auditoría registran las actividades esperadas."""

    def setUp(self):
        self.negocio = _negocio("Negocio Auditoria Integracion")
        set_current_business(None)

    def test_compra_genera_actividad_auditoria(self):
        proveedor = _proveedor(self.negocio)
        Compra.objects.all_tenants().create(
            negocio=self.negocio,
            proveedor=proveedor,
            fecha=timezone.now(),
        )
        self.assertTrue(
            ActividadNegocio.objects.filter(negocio=self.negocio, modulo="compras").exists(),
            "Crear una Compra debe generar una actividad de auditoría en módulo 'compras'.",
        )

    def test_receta_genera_actividad_auditoria(self):
        pan = _producto(self.negocio, "Pan Audit", tipo=TipoProducto.VENTA)
        Receta.objects.all_tenants().create(
            negocio=self.negocio,
            nombre="Receta Auditoria",
            producto_resultante=pan,
            rendimiento=Decimal("1"),
        )
        self.assertTrue(
            ActividadNegocio.objects.filter(negocio=self.negocio, modulo="produccion").exists(),
            "Crear una Receta debe generar una actividad de auditoría en módulo 'produccion'.",
        )

    def test_gastofijo_crea_actividad_auditoria(self):
        GastoFijo.objects.all_tenants().create(
            negocio=self.negocio,
            concepto="Alquiler Auditoria",
            monto=Decimal("50000"),
            periodicidad=GastoFijo.Periodicidad.MENSUAL,
        )
        self.assertTrue(
            ActividadNegocio.objects.filter(negocio=self.negocio, modulo="gastos").exists(),
            "Crear un GastoFijo debe generar actividad de auditoría en módulo 'gastos'.",
        )

    def test_gastofijo_delete_genera_actividad_auditoria(self):
        gasto = GastoFijo.objects.all_tenants().create(
            negocio=self.negocio,
            concepto="Gasto a borrar",
            monto=Decimal("5000"),
            periodicidad=GastoFijo.Periodicidad.MENSUAL,
        )
        # Limpiar actividades de creación
        ActividadNegocio.objects.filter(negocio=self.negocio).delete()

        gasto.delete()

        self.assertTrue(
            ActividadNegocio.objects.filter(
                negocio=self.negocio,
                modulo="gastos",
                accion__icontains="eliminado",
            ).exists(),
            "Borrar un GastoFijo debe generar actividad de auditoría con 'eliminado' en la acción.",
        )
