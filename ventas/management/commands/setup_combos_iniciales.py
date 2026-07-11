"""Configura, para un negocio real ya cargado, los combos de la lista original
del cliente y vincula las "Media X"/"Porción X" sueltas que hoy son productos
independientes (y quedaron en stock negativo) a la torta/pastafrola madre
correspondiente, vía PresentacionVenta con factor fraccionario — para que
descuenten del stock real en vez de ser productos fantasma desconectados.

Por defecto corre en modo DRY-RUN (solo imprime el plan, no escribe nada).
Revisá el plan con cuidado — hay mapeos de nombre ambiguos marcados con
"⚠" (ej. "Frola" sin sabor, "membrillo o batata") que puede que necesiten
ajuste manual antes de aplicar.

Uso:
    uv run python manage.py setup_combos_iniciales --negocio "Nombre exacto"
    uv run python manage.py setup_combos_iniciales --negocio "Nombre exacto" --aplicar
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Negocio
from stock.models import Producto
from ventas.models import Combo, ComboItem, PresentacionVenta

# nombre_producto_madre -> porciones por unidad entera
PORCIONES_POR_PRODUCTO = {
    "Tarta de ricota": 4,
    "Bizcochuelo vainilla": 4,
    "Bizcochuelo Marmolado": 4,
    "Tarta toffi": 4,
    "Budín Napolitano": 16,
    "Pastafrola de Membrillo": 4,
    "Pastafrola de Batata": 4,
}

# producto_suelto_a_desactivar -> (producto_madre, nombre_presentacion, factor, precio, advertencia)
PRESENTACIONES_A_MIGRAR = [
    ("Media tarta de ricota", "Tarta de ricota", "Media", "0.5", "5000", None),
    ("Porción de ricota", "Tarta de ricota", "Porción", "0.25", "2600", None),
    ("Porción mármolado", "Bizcochuelo Marmolado", "Porción", "0.25", "1600",
     "⚠ Hay dos productos 'Porción mármolado' duplicados ($1600 y $1900). Se usa el de $1600; revisá y borrá el otro manualmente."),
    ("Porción tofi", "Tarta toffi", "Porción", "0.25", "2800", None),
    ("Porción vainilla", "Bizcochuelo vainilla", "Porción", "0.25", "1600", None),
    ("Medio vainilla", "Bizcochuelo vainilla", "Media", "0.5", "3000", None),
    ("Porción batata", "Pastafrola de Batata", "Porción", "0.25", "2100", None),
    ("Media Pastafrola", "Pastafrola de Membrillo", "Media", "0.5", "4100",
     "⚠ 'Media Pastafrola' no dice el sabor — se asumió Membrillo. Revisá si corresponde a Batata."),
    ("Facturas 1/2 doc.", "1 Factura", "Media docena", "6", "4000", None),
]

# nombre_combo, precio, [(producto, cantidad_entera_o_None, porciones_o_None)], advertencia
COMBOS = [
    ("Combo 1", "6900", [("Bizcochuelo vainilla", 1, None), ("Tarta de ricota", 1, None), ("Tarta toffi", 1, None)], None),
    ("Combo 2", "5800", [("Bizcochuelo vainilla", 1, None), ("Pastafrola de Membrillo", 1, None), ("Tarta de ricota", 1, None)], None),
    ("Combo 3", "6100", [("Bizcochuelo Marmolado", 1, None), ("Tarta de ricota", 1, None), ("Pastafrola de Membrillo", 1, None)], None),
    ("Combo 4", "4800", [("Bizcochuelo vainilla", 1, None), ("Pastafrola de Membrillo", 1, None), ("Budín Napolitano", 2, None)],
     "⚠ 'Frola' sin sabor especificado — se asumió Pastafrola de Membrillo."),
    ("Combo 5", "7400", [("Bizcochuelo Marmolado", 1, None), ("Tarta de ricota", 1, None), ("Pastafrola de Membrillo", 1, None), ("Budín Napolitano", 2, None)],
     "⚠ 'Frola' sin sabor especificado — se asumió Pastafrola de Membrillo."),
    ("Combo 6", "7600", [("Bizcochuelo vainilla", 1, None), ("Tarta de ricota", 1, None)], None),
    ("Combo 7", "6200", [("Bizcochuelo Marmolado", None, 2), ("Bizcochuelo vainilla", None, 2)], None),
    ("Combo 8", "10300", [("Tarta toffi", None, 2), ("Tarta de ricota", None, 2)], None),
    ("Combo 9", "8900", [("Bizcochuelo Marmolado", None, 2), ("Tarta toffi", None, 2)], None),
    ("Combo 10", "9500", [("Tarta toffi", None, 2), ("Pastafrola de Membrillo", None, 2)],
     "⚠ La mitad puede ser membrillo o batata a elección del cliente — se armó fijo con Membrillo; para Batata cargar un Combo aparte."),
    ("Combo 11", "7100", [("Bizcochuelo Marmolado", None, 2), ("Tarta de ricota", None, 1), ("Budín Napolitano", 2, None)], None),
    ("Combo 12", "8800", [("Pastafrola de Membrillo", None, 2), ("Tarta de ricota", None, 2)],
     "⚠ La mitad puede ser membrillo o batata a elección del cliente — se armó fijo con Membrillo; para Batata cargar un Combo aparte."),
    ("Combo 13", "8100", [("Tarta de ricota", None, 2), ("Bizcochuelo Marmolado", None, 2)], None),
]


class Command(BaseCommand):
    help = "Configura combos y vincula presentaciones fraccionarias para un negocio real (ver docstring)."

    def add_arguments(self, parser):
        parser.add_argument("--negocio", required=True, help="Nombre exacto del Negocio a configurar.")
        parser.add_argument("--aplicar", action="store_true", help="Escribe los cambios (por defecto solo imprime el plan).")

    def handle(self, *args, **options):
        try:
            negocio = Negocio.objects.get(nombre=options["negocio"])
        except Negocio.DoesNotExist:
            raise CommandError(f"No existe un Negocio con nombre exacto '{options['negocio']}'.")
        except Negocio.MultipleObjectsReturned:
            raise CommandError(f"Hay más de un Negocio con nombre '{options['negocio']}'; usá el ID en el shell en su lugar.")

        aplicar = options["aplicar"]
        self.stdout.write(self.style.WARNING(
            "MODO DRY-RUN (no se escribe nada). Pasá --aplicar para confirmar."
            if not aplicar else "Aplicando cambios…"
        ))

        with transaction.atomic():
            self._configurar_porciones(negocio, aplicar)
            self._migrar_presentaciones(negocio, aplicar)
            self._crear_combos(negocio, aplicar)
            if not aplicar:
                transaction.set_rollback(True)

    def _producto(self, negocio, nombre):
        return Producto.objects.all_tenants().filter(negocio=negocio, nombre__iexact=nombre).first()

    def _configurar_porciones(self, negocio, aplicar):
        self.stdout.write("\n== Porciones por unidad ==")
        for nombre, porciones in PORCIONES_POR_PRODUCTO.items():
            p = self._producto(negocio, nombre)
            if not p:
                self.stdout.write(self.style.ERROR(f"  ✗ No encontrado: '{nombre}' — omitido."))
                continue
            self.stdout.write(f"  {nombre}: porciones_por_unidad {p.porciones_por_unidad} -> {porciones}")
            if aplicar:
                p.porciones_por_unidad = porciones
                p.save(update_fields=["porciones_por_unidad"])

    def _migrar_presentaciones(self, negocio, aplicar):
        self.stdout.write("\n== Presentaciones fraccionarias (Media/Porción sueltas) ==")
        for nombre_suelto, nombre_madre, nombre_pv, factor, precio, warning in PRESENTACIONES_A_MIGRAR:
            madre = self._producto(negocio, nombre_madre)
            suelto = self._producto(negocio, nombre_suelto)
            if warning:
                self.stdout.write(self.style.WARNING(f"  {warning}"))
            if not madre:
                self.stdout.write(self.style.ERROR(f"  ✗ Producto madre no encontrado: '{nombre_madre}' — omitido."))
                continue
            self.stdout.write(
                f"  {nombre_suelto or '(sin producto suelto)'} -> "
                f"PresentacionVenta('{nombre_pv}', factor={factor}, precio=${precio}) de '{nombre_madre}'"
            )
            if aplicar:
                PresentacionVenta.objects.all_tenants().update_or_create(
                    negocio=negocio, producto=madre, nombre=nombre_pv,
                    defaults={"factor": Decimal(factor), "precio": Decimal(precio), "activo": True},
                )
                if suelto and suelto.pk != madre.pk:
                    suelto.activo = False
                    suelto.save(update_fields=["activo"])
                    self.stdout.write(f"    -> '{nombre_suelto}' desactivado (queda oculto del POS, no se borra).")

    def _crear_combos(self, negocio, aplicar):
        self.stdout.write("\n== Combos ==")
        for nombre, precio, items, warning in COMBOS:
            if warning:
                self.stdout.write(self.style.WARNING(f"  {warning}"))
            self.stdout.write(f"  {nombre} (${precio}):")
            productos_ok = True
            resolved = []
            for nombre_prod, cantidad, porciones in items:
                p = self._producto(negocio, nombre_prod)
                if not p:
                    self.stdout.write(self.style.ERROR(f"    ✗ Producto no encontrado: '{nombre_prod}' — combo omitido."))
                    productos_ok = False
                    continue
                etiqueta = f"{porciones} porciones de {nombre_prod}" if porciones else f"{cantidad} × {nombre_prod}"
                self.stdout.write(f"    - {etiqueta}")
                resolved.append((p, cantidad, porciones))
            if not productos_ok:
                continue
            if aplicar:
                combo, _ = Combo.objects.all_tenants().update_or_create(
                    negocio=negocio, nombre=nombre,
                    defaults={"precio": Decimal(precio), "activo": True},
                )
                combo.items.all().delete()
                for p, cantidad, porciones in resolved:
                    ComboItem.objects.all_tenants().create(
                        negocio=negocio, combo=combo, producto=p,
                        cantidad=cantidad or 1, porciones=porciones,
                    )
