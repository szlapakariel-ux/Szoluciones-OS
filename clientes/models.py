from django.db import models

from core.models import TenantOwnedModel


class Cliente(TenantOwnedModel):
    nombre = models.CharField("Nombre", max_length=120)
    telefono = models.CharField("Teléfono", max_length=40, blank=True)
    email = models.EmailField("Email", blank=True)
    direccion = models.CharField("Dirección", max_length=200, blank=True)
    fecha_alta = models.DateField("Fecha de alta", auto_now_add=True)
    cumpleanios = models.DateField("Cumpleaños", null=True, blank=True)
    notas = models.TextField("Notas", blank=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
