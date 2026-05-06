from django.apps import AppConfig


class StockConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "stock"
    verbose_name = "Stock"

    def ready(self):
        from . import signals  # noqa: F401
