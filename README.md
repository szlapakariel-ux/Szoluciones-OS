# Szoluciones OS

Software de gestión operativa para PyMEs. MVP web hosteado multi-cliente con 7 módulos: Compras, Stock, Producción, Ventas, Clientes, Caja diaria y Gastos fijos.

## Stack

- Python 3.12+ · Django 5.x · django-unfold (admin moderno)
- SQLite (cambiar a PostgreSQL antes de producción real)
- Multi-tenant por *shared schema*: cada modelo tiene FK a `Negocio` y un middleware filtra por el negocio del usuario logueado.

## Setup local

Requisitos: [`uv`](https://github.com/astral-sh/uv) instalado.

```bash
# 1. Sincronizar dependencias
uv sync

# 2. Variables de entorno
cp .env.example .env

# 3. Crear las tablas
uv run python manage.py migrate

# 4. Cargar datos demo (negocio piloto, productos, ventas, etc.)
uv run python manage.py seed_demo

# 5. Levantar el servidor
uv run python manage.py runserver
```

Entrar a <http://127.0.0.1:8000/admin/> con:

- **Superusuario** (todos los negocios): `admin` / `admin`
- **Dueño del piloto** (solo ve "Panadería Piloto"): `duenio` / `duenio1234`

Para resembrar desde cero:

```bash
uv run python manage.py seed_demo --reset
```

## Estructura

```
szoluciones_os/   # config Django (settings, urls, wsgi)
core/             # Negocio, Usuario, TenantOwnedModel, middleware, dashboard
stock/            # Producto, MovimientoStock
compras/          # Proveedor, Compra, ItemCompra
clientes/         # Cliente
ventas/           # Venta, ItemVenta
produccion/       # Receta, Ingrediente
caja/             # MovimientoCaja
gastos/           # GastoFijo
```

## Cómo funciona el multi-tenant

1. Cada `Usuario` tiene un FK a `Negocio`.
2. `core.middleware.CurrentBusinessMiddleware` guarda `request.user.negocio` en un threadlocal por request.
3. `core.managers.TenantManager` filtra todos los querysets por ese negocio automáticamente.
4. `core.admin.TenantOwnedAdmin` (clase base de todos los `ModelAdmin`) refuerza el filtro en `get_queryset` y completa `obj.negocio` al guardar.

Resultado: cada usuario solo ve los datos de SU negocio sin que cada vista lo tenga que pedir explícitamente.

## Reglas automáticas

- Crear una **Compra** + items → genera `MovimientoStock` (INGRESO) por cada item y un `MovimientoCaja` (EGRESO) por el total.
- Crear una **Venta** + items → genera `MovimientoStock` (EGRESO) y un `MovimientoCaja` (INGRESO).
- `Producto.stock_actual` se ajusta solo a partir de los movimientos.

## Crear un nuevo negocio piloto

```bash
uv run python manage.py shell
```

```python
from core.models import Negocio, Usuario
from django.contrib.auth.models import Permission

n = Negocio.objects.create(nombre="Mi Negocio", rubro="Almacén")
u = Usuario.objects.create_user(
    username="duenio_x", password="cambiar123",
    is_staff=True, negocio=n,
)
perms = Permission.objects.filter(
    content_type__app_label__in=[
        "stock", "compras", "clientes", "ventas",
        "produccion", "caja", "gastos",
    ]
)
u.user_permissions.set(perms)
```

## Lo que falta (en orden de prioridad)

- Pantallas mobile-first custom para Venta en mostrador, Caja del día y ver Stock.
- Dashboard con gráficos (ventas por día, top productos, mix de métodos de pago).
- Migrar a PostgreSQL.
- Definir métrica de "crecimiento" para el modelo de comisiones.
- Despliegue en la nube + dominio.
- API REST para integraciones IA.
- Tests automatizados.

## Verificación que pasó este MVP

- [x] `manage.py check` sin errores.
- [x] Migraciones limpias.
- [x] `seed_demo` crea negocio piloto + 5 productos + 3 clientes + 2 compras + 5 ventas + recetas + gastos.
- [x] Admin con tema **Szoluciones OS**, sidebar reordenado al flujo del dueño.
- [x] KPIs en la home: ventas de hoy, caja actual, productos bajo stock mínimo, semana en curso.
- [x] Las compras crean automáticamente MovimientoStock + MovimientoCaja.
- [x] Las ventas crean automáticamente MovimientoStock + MovimientoCaja.
- [x] Aislamiento multi-tenant: con un segundo negocio + usuario, ese usuario solo ve sus propios productos, ventas, clientes y movimientos.
