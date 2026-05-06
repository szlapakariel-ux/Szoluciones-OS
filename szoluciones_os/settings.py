"""
Django settings for Szoluciones OS.
"""

import os
from pathlib import Path

from django.urls import reverse_lazy
from dotenv import load_dotenv
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-dev-only-change-me-szoluciones-os",
)
DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,.railway.app").split(",")
    if h.strip()
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "https://*.railway.app,https://*.up.railway.app",
    ).split(",")
    if o.strip()
]

# Railway expone el dominio público en RAILWAY_PUBLIC_DOMAIN. Lo agregamos
# a ALLOWED_HOSTS y CSRF_TRUSTED_ORIGINS automáticamente para no depender
# del wildcard (que en algunos casos no es suficiente).
_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _railway_domain and _railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_domain)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_railway_domain}")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "stock",
    "compras",
    "clientes",
    "ventas",
    "produccion",
    "caja",
    "gastos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.CurrentBusinessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "szoluciones_os.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates", BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "szoluciones_os.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "core.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "core" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"

UNFOLD = {
    "SITE_TITLE": "Szoluciones OS",
    "SITE_HEADER": "Szoluciones OS",
    "SITE_SUBHEADER": "Gestión operativa para tu negocio",
    "SITE_SYMBOL": "storefront",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_BACK_BUTTON": True,
    "THEME": None,
    "BORDER_RADIUS": "8px",
    "COLORS": {
        "base": {
            "50": "249 250 251",
            "100": "243 244 246",
            "200": "229 231 235",
            "300": "209 213 219",
            "400": "156 163 175",
            "500": "107 114 128",
            "600": "75 85 99",
            "700": "55 65 81",
            "800": "31 41 55",
            "900": "17 24 39",
            "950": "3 7 18",
        },
        "primary": {
            "50": "240 253 250",
            "100": "204 251 241",
            "200": "153 246 228",
            "300": "94 234 212",
            "400": "45 212 191",
            "500": "20 184 166",
            "600": "13 148 136",
            "700": "15 118 110",
            "800": "17 94 89",
            "900": "19 78 74",
            "950": "4 47 46",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Operaciones diarias",
                "separator": True,
                "items": [
                    {
                        "title": "Caja",
                        "icon": "account_balance_wallet",
                        "link": reverse_lazy("admin:caja_movimientocaja_changelist"),
                    },
                    {
                        "title": "Ventas",
                        "icon": "point_of_sale",
                        "link": reverse_lazy("admin:ventas_venta_changelist"),
                    },
                    {
                        "title": "Stock",
                        "icon": "inventory_2",
                        "link": reverse_lazy("admin:stock_producto_changelist"),
                    },
                ],
            },
            {
                "title": "Operaciones de fondo",
                "separator": True,
                "items": [
                    {
                        "title": "Compras",
                        "icon": "shopping_cart",
                        "link": reverse_lazy("admin:compras_compra_changelist"),
                    },
                    {
                        "title": "Recetas",
                        "icon": "restaurant",
                        "link": reverse_lazy("admin:produccion_receta_changelist"),
                    },
                    {
                        "title": "Ejecutar producción",
                        "icon": "local_fire_department",
                        "link": reverse_lazy("admin:produccion_produccionrealizada_changelist"),
                    },
                    {
                        "title": "Clientes",
                        "icon": "groups",
                        "link": reverse_lazy("admin:clientes_cliente_changelist"),
                    },
                    {
                        "title": "Gastos fijos",
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:gastos_gastofijo_changelist"),
                    },
                ],
            },
            {
                "title": "Configuración",
                "separator": True,
                "items": [
                    {
                        "title": "Negocios",
                        "icon": "store",
                        "link": reverse_lazy("admin:core_negocio_changelist"),
                    },
                    {
                        "title": "Usuarios",
                        "icon": "person",
                        "link": reverse_lazy("admin:core_usuario_changelist"),
                    },
                ],
            },
        ],
    },
    "DASHBOARD_CALLBACK": "core.dashboard.dashboard_callback",
}
