from decimal import Decimal

from django.test import TestCase

from core.models import Negocio
from .models import EstadoUnidadFisica, MovimientoStock, Producto, TipoProducto, UnidadFisica
from .servicios import (
    StockInsuficienteError,
    consumir_entera,
    consumir_enteras,
    consumir_porciones,
    crear_unidades_cerradas,
    revertir_entera,
    revertir_porciones,
)


def _negocio(nombre="Negocio Test"):
    return Negocio.objects.create(nombre=nombre)


def _torta(negocio, nombre="Torta Vainilla", porciones_por_unidad=4):
    return Producto.objects.all_tenants().create(
        negocio=negocio,
        nombre=nombre,
        tipo=TipoProducto.VENTA,
        costo=Decimal("500"),
        precio_venta=Decimal("2000"),
        porciones_por_unidad=porciones_por_unidad,
    )


class CrearUnidadesCerradasTest(TestCase):
    def setUp(self):
        self.negocio = _negocio()
        self.producto = _torta(self.negocio)

    def test_crea_n_unidades_cerradas(self):
        crear_unidades_cerradas(self.producto, 3)
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(
                producto=self.producto, estado=EstadoUnidadFisica.CERRADA
            ).count(),
            3,
        )

    def test_cantidad_cero_no_crea_nada(self):
        crear_unidades_cerradas(self.producto, 0)
        self.assertEqual(UnidadFisica.objects.all_tenants().filter(producto=self.producto).count(), 0)

    def test_ingreso_por_compra_genera_unidades_cerradas(self):
        MovimientoStock.objects.all_tenants().create(
            negocio=self.negocio,
            producto=self.producto,
            tipo=MovimientoStock.Tipo.INGRESO,
            cantidad=Decimal("5"),
            motivo="Compra test",
        )
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(
                producto=self.producto, estado=EstadoUnidadFisica.CERRADA
            ).count(),
            5,
        )

    def test_producto_no_fraccionable_no_genera_unidades(self):
        simple = Producto.objects.all_tenants().create(
            negocio=self.negocio, nombre="Factura", tipo=TipoProducto.VENTA,
            precio_venta=Decimal("100"),
        )
        MovimientoStock.objects.all_tenants().create(
            negocio=self.negocio, producto=simple, tipo=MovimientoStock.Tipo.INGRESO,
            cantidad=Decimal("10"), motivo="Compra test",
        )
        self.assertEqual(UnidadFisica.objects.all_tenants().filter(producto=simple).count(), 0)


class ConsumirEnteraTest(TestCase):
    def setUp(self):
        self.negocio = _negocio()
        self.producto = _torta(self.negocio)

    def test_consume_una_cerrada(self):
        crear_unidades_cerradas(self.producto, 2)
        consumir_entera(self.producto)
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(
                producto=self.producto, estado=EstadoUnidadFisica.CERRADA
            ).count(),
            1,
        )
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(
                producto=self.producto, estado=EstadoUnidadFisica.AGOTADA
            ).count(),
            1,
        )

    def test_sin_cerradas_lanza_error(self):
        with self.assertRaises(StockInsuficienteError):
            consumir_entera(self.producto)

    def test_solo_hay_abiertas_no_permite_vender_entera(self):
        """El caso real reportado: el mostrador tiene todo abierto (fraccionado),
        y aunque sumen varias porciones sueltas, no hay ninguna torta cerrada
        para vender entera."""
        unidades = crear_unidades_cerradas(self.producto, 3)
        # Simula que las 3 tortas ya se abrieron y quedan porciones sueltas de cada una.
        for u in unidades:
            u.estado = EstadoUnidadFisica.ABIERTA
            u.porciones_restantes = 3
            u.save(update_fields=["estado", "porciones_restantes"])
        with self.assertRaises(StockInsuficienteError):
            consumir_entera(self.producto)

    def test_consumir_enteras_multiples(self):
        crear_unidades_cerradas(self.producto, 3)
        consumir_enteras(self.producto, 2)
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(
                producto=self.producto, estado=EstadoUnidadFisica.CERRADA
            ).count(),
            1,
        )


class ConsumirPorcionesTest(TestCase):
    def setUp(self):
        self.negocio = _negocio()
        self.producto = _torta(self.negocio, porciones_por_unidad=4)

    def test_abre_unidad_cerrada_si_no_hay_abiertas(self):
        crear_unidades_cerradas(self.producto, 1)
        consumir_porciones(self.producto, 2)
        unidad = UnidadFisica.objects.all_tenants().get(producto=self.producto)
        self.assertEqual(unidad.estado, EstadoUnidadFisica.ABIERTA)
        self.assertEqual(unidad.porciones_restantes, 2)

    def test_consume_de_abierta_existente_antes_de_abrir_otra(self):
        crear_unidades_cerradas(self.producto, 2)
        consumir_porciones(self.producto, 1)  # abre una, quedan 3 porciones
        consumir_porciones(self.producto, 1)  # sigue consumiendo de la misma abierta
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(estado=EstadoUnidadFisica.CERRADA).count(),
            1,
        )
        abierta = UnidadFisica.objects.all_tenants().get(estado=EstadoUnidadFisica.ABIERTA)
        self.assertEqual(abierta.porciones_restantes, 2)

    def test_agota_unidad_al_llegar_a_cero(self):
        crear_unidades_cerradas(self.producto, 1)
        consumir_porciones(self.producto, 4)
        unidad = UnidadFisica.objects.all_tenants().get(producto=self.producto)
        self.assertEqual(unidad.estado, EstadoUnidadFisica.AGOTADA)
        self.assertEqual(unidad.porciones_restantes, 0)

    def test_consumo_abarca_varias_unidades(self):
        crear_unidades_cerradas(self.producto, 2)
        consumir_porciones(self.producto, 6)  # 4 de una + 2 de otra
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(estado=EstadoUnidadFisica.AGOTADA).count(),
            1,
        )
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(estado=EstadoUnidadFisica.ABIERTA).count(),
            1,
        )

    def test_sin_stock_suficiente_lanza_error(self):
        crear_unidades_cerradas(self.producto, 1)
        with self.assertRaises(StockInsuficienteError):
            consumir_porciones(self.producto, 8)  # solo hay 4 porciones disponibles


class RevertirTest(TestCase):
    def setUp(self):
        self.negocio = _negocio()
        self.producto = _torta(self.negocio, porciones_por_unidad=4)

    def test_revertir_entera_repone_cerrada(self):
        revertir_entera(self.producto)
        self.assertEqual(
            UnidadFisica.objects.all_tenants().filter(
                producto=self.producto, estado=EstadoUnidadFisica.CERRADA
            ).count(),
            1,
        )

    def test_revertir_porciones_sin_abiertas_crea_una(self):
        revertir_porciones(self.producto, 2)
        unidad = UnidadFisica.objects.all_tenants().get(producto=self.producto)
        self.assertEqual(unidad.estado, EstadoUnidadFisica.ABIERTA)
        self.assertEqual(unidad.porciones_restantes, 2)

    def test_revertir_porciones_suma_a_abierta_existente(self):
        crear_unidades_cerradas(self.producto, 1)
        consumir_porciones(self.producto, 3)  # queda abierta con 1 restante
        revertir_porciones(self.producto, 2)
        unidad = UnidadFisica.objects.all_tenants().get(producto=self.producto)
        self.assertEqual(unidad.porciones_restantes, 3)

    def test_revertir_porciones_no_supera_capacidad_de_una_unidad(self):
        crear_unidades_cerradas(self.producto, 1)
        consumir_porciones(self.producto, 4)  # queda agotada
        revertir_porciones(self.producto, 4)
        total = sum(
            u.porciones_restantes
            for u in UnidadFisica.objects.all_tenants().filter(producto=self.producto)
            if u.estado != EstadoUnidadFisica.CERRADA
        )
        self.assertEqual(total, 4)
