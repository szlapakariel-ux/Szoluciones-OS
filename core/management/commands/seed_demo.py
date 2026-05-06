"""Carga datos demo para que el sistema sea explorable apenas se instala.

Crea:
- 1 Negocio "Panadería Piloto" + 1 superusuario (admin / admin) sin negocio
- 1 usuario "duenio" con password "duenio1234" asignado al negocio
- 5 productos, 3 clientes, 2 proveedores, 1 receta, 2 compras, 5 ventas,
  algunos gastos fijos.

Uso:
    uv run python manage.py seed_demo
    uv run python manage.py seed_demo --reset   # borra todo antes
"""

from datetime import timedelta
from decimal import Decimal
from random import Random

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from caja.models import MovimientoCaja
from clientes.models import Cliente
from compras.models import Compra, ItemCompra, Proveedor
from core.managers import set_current_business
from core.models import Negocio
from gastos.models import GastoFijo
from produccion.models import Ingrediente, Receta
from stock.models import MovimientoStock, Producto
from ventas.models import ItemVenta, Venta


class Command(BaseCommand):
    help = "Carga datos demo en un negocio piloto."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra todos los datos existentes antes de sembrar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        Usuario = get_user_model()
        rnd = Random(42)

        if options["reset"]:
            self.stdout.write("Borrando datos previos…")
            for model in [
                MovimientoCaja, ItemVenta, Venta, ItemCompra, Compra, Proveedor,
                Ingrediente, Receta, MovimientoStock, Producto, Cliente,
                GastoFijo,
            ]:
                model.objects.all_tenants().delete()
            Usuario.objects.exclude(is_superuser=True).delete()
            Negocio.objects.all().delete()

        # Superusuario
        if not Usuario.objects.filter(username="admin").exists():
            Usuario.objects.create_superuser(
                username="admin", password="admin", email="admin@szoluciones.local"
            )
            self.stdout.write(self.style.SUCCESS("[OK] Superusuario admin / admin creado"))

        # Superusuario principal del owner
        if not Usuario.objects.filter(username="ariel").exists():
            Usuario.objects.create_superuser(
                username="ariel", password="admin", email="ariel@szoluciones.local"
            )
            self.stdout.write(self.style.SUCCESS("[OK] Superusuario ariel / admin creado"))

        negocio, _ = Negocio.objects.get_or_create(
            nombre="Panadería Piloto",
            defaults={
                "rubro": "Panadería",
                "telefono": "+54 9 11 5555-1234",
                "direccion": "Av. Siempre Viva 742",
                "cuit": "30-71234567-8",
            },
        )
        self.stdout.write(f"[OK] Negocio: {negocio}")

        # Activamos el contexto de tenant para que el TenantManager filtre
        set_current_business(None)

        usr = Usuario.objects.filter(username="duenio").first()
        if not usr:
            usr = Usuario.objects.create_user(
                username="duenio",
                password="duenio1234",
                email="duenio@panaderiapiloto.local",
                first_name="Ariel",
                last_name="Dueño",
                is_staff=True,
                negocio=negocio,
            )
            self.stdout.write(self.style.SUCCESS("[OK] Usuario duenio / duenio1234 creado"))
        # Permisos: dueño puede ver/agregar/cambiar/borrar todo lo de su negocio
        # (el filtro multi-tenant del admin se encarga de que solo vea lo suyo).
        app_labels = [
            "core", "stock", "compras", "clientes", "ventas",
            "produccion", "caja", "gastos",
        ]
        # Excluimos Negocio y Usuario de los permisos del dueño (solo superuser)
        perms = Permission.objects.filter(
            content_type__app_label__in=app_labels
        ).exclude(
            content_type__model__in=["negocio", "usuario"]
        )
        usr.user_permissions.set(perms)

        # --- Productos ---
        productos_data = [
            ("Pan francés", "PAN001", "KG", "1500", "300", "200"),
            ("Medialunas", "MED001", "DC", "3000", "1200", "180"),
            ("Harina 000", "HAR000", "KG", "1200", "800", "10"),
            ("Manteca", "MAN001", "KG", "4500", "3500", "5"),
            ("Café molido 250g", "CAF250", "UN", "3500", "2200", "20"),
        ]
        productos = {}
        for nombre, codigo, unidad, precio, costo, stock_min in productos_data:
            p, _ = Producto.objects.all_tenants().get_or_create(
                negocio=negocio,
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "unidad_medida": unidad,
                    "precio_venta": Decimal(precio),
                    "costo": Decimal(costo),
                    "stock_minimo": Decimal(stock_min),
                },
            )
            productos[codigo] = p
        self.stdout.write(f"[OK] {len(productos)} productos")

        # --- Clientes ---
        clientes_data = [
            ("María González", "+54 9 11 4444-1111", "maria@example.com"),
            ("Roberto Pérez", "+54 9 11 4444-2222", "roberto@example.com"),
            ("Lucía Fernández", "", ""),
        ]
        clientes = []
        for nombre, tel, email in clientes_data:
            c, _ = Cliente.objects.all_tenants().get_or_create(
                negocio=negocio,
                nombre=nombre,
                defaults={"telefono": tel, "email": email},
            )
            clientes.append(c)
        self.stdout.write(f"[OK] {len(clientes)} clientes")

        # --- Proveedores ---
        prov1, _ = Proveedor.objects.all_tenants().get_or_create(
            negocio=negocio,
            nombre="Molinos del Sur",
            defaults={"telefono": "+54 11 4222-3333", "email": "ventas@molinosdelsur.local"},
        )
        prov2, _ = Proveedor.objects.all_tenants().get_or_create(
            negocio=negocio,
            nombre="Lácteos La Vaca",
            defaults={"telefono": "+54 11 4222-4444"},
        )

        # --- Compras (con items, dispararán signals de stock) ---
        if not Compra.objects.all_tenants().filter(negocio=negocio).exists():
            ahora = timezone.now()
            compra1 = Compra.objects.create(
                negocio=negocio,
                proveedor=prov1,
                fecha=ahora - timedelta(days=3),
                observaciones="Reposición semanal de harina",
            )
            ItemCompra.objects.create(
                negocio=negocio, compra=compra1,
                producto=productos["HAR000"],
                cantidad=Decimal("50"), precio_unitario=Decimal("750"),
            )
            compra1.recalcular_total()
            MovimientoCaja.objects.create(
                negocio=negocio, fecha=compra1.fecha,
                tipo=MovimientoCaja.Tipo.EGRESO, monto=compra1.total,
                concepto=f"Compra a {prov1}", compra_origen=compra1,
            )

            compra2 = Compra.objects.create(
                negocio=negocio, proveedor=prov2,
                fecha=ahora - timedelta(days=1),
                observaciones="Manteca + café para el lunes",
            )
            ItemCompra.objects.create(
                negocio=negocio, compra=compra2,
                producto=productos["MAN001"],
                cantidad=Decimal("10"), precio_unitario=Decimal("3200"),
            )
            ItemCompra.objects.create(
                negocio=negocio, compra=compra2,
                producto=productos["CAF250"],
                cantidad=Decimal("20"), precio_unitario=Decimal("2000"),
            )
            compra2.recalcular_total()
            MovimientoCaja.objects.create(
                negocio=negocio, fecha=compra2.fecha,
                tipo=MovimientoCaja.Tipo.EGRESO, monto=compra2.total,
                concepto=f"Compra a {prov2}", compra_origen=compra2,
            )
            self.stdout.write("[OK] 2 compras")

        # --- Ventas ---
        if not Venta.objects.all_tenants().filter(negocio=negocio).exists():
            ahora = timezone.now()
            ventas_specs = [
                (clientes[0], [("PAN001", "2"), ("MED001", "1")], "EFECTIVO", 0),
                (clientes[1], [("CAF250", "2")], "MP", 1),
                (None,        [("PAN001", "0.5")], "EFECTIVO", 0),
                (clientes[2], [("MED001", "2"), ("CAF250", "1")], "DEBITO", 0),
                (None,        [("PAN001", "1"), ("MED001", "0.5")], "EFECTIVO", 0),
            ]
            for cli, items, mp, dias_atras in ventas_specs:
                v = Venta.objects.create(
                    negocio=negocio, cliente=cli,
                    fecha=ahora - timedelta(days=dias_atras, minutes=rnd.randint(10, 600)),
                    metodo_pago=mp,
                )
                for codigo, cant in items:
                    ItemVenta.objects.create(
                        negocio=negocio, venta=v,
                        producto=productos[codigo],
                        cantidad=Decimal(cant),
                        precio_unitario=productos[codigo].precio_venta,
                    )
                v.recalcular_total()
                cliente_str = f" a {cli}" if cli else ""
                MovimientoCaja.objects.create(
                    negocio=negocio, fecha=v.fecha,
                    tipo=MovimientoCaja.Tipo.INGRESO, monto=v.total,
                    concepto=f"Venta{cliente_str}",
                    metodo_pago=mp, venta_origen=v,
                )
            self.stdout.write("[OK] 5 ventas")

        # --- Receta ---
        if not Receta.objects.all_tenants().filter(negocio=negocio).exists():
            receta = Receta.objects.create(
                negocio=negocio,
                nombre="Medialunas de manteca (docena)",
                producto_resultante=productos["MED001"],
                rendimiento=Decimal("1"),
                instrucciones="Amasar, dejar levar, hornear 12 minutos a 200°C.",
            )
            Ingrediente.objects.create(
                negocio=negocio, receta=receta,
                producto=productos["HAR000"], cantidad=Decimal("0.5"),
            )
            Ingrediente.objects.create(
                negocio=negocio, receta=receta,
                producto=productos["MAN001"], cantidad=Decimal("0.2"),
            )
            self.stdout.write("[OK] 1 receta")

        # --- Gastos fijos ---
        gastos_data = [
            ("Alquiler local", "180000", "MENSUAL"),
            ("Luz", "35000", "MENSUAL"),
            ("Internet", "12000", "MENSUAL"),
            ("Sueldo ayudante", "350000", "MENSUAL"),
        ]
        for concepto, monto, periodicidad in gastos_data:
            GastoFijo.objects.all_tenants().get_or_create(
                negocio=negocio,
                concepto=concepto,
                defaults={
                    "monto": Decimal(monto),
                    "periodicidad": periodicidad,
                    "proximo_vencimiento": timezone.localdate() + timedelta(days=10),
                },
            )
        self.stdout.write(f"[OK] {len(gastos_data)} gastos fijos")

        self.stdout.write(self.style.SUCCESS(""))
        self.stdout.write(self.style.SUCCESS("Listo. Entrá al admin con:"))
        self.stdout.write("  - Superusuario: admin / admin")
        self.stdout.write("  - Dueno piloto: duenio / duenio1234")
        self.stdout.write("  http://localhost:8000/admin/")
