from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import TenantManager


class Negocio(models.Model):
    nombre = models.CharField("Nombre del negocio", max_length=120)
    rubro = models.CharField("Rubro", max_length=80, blank=True)
    telefono = models.CharField("Teléfono", max_length=40, blank=True)
    direccion = models.CharField("Dirección", max_length=200, blank=True)
    cuit = models.CharField("CUIT", max_length=20, blank=True)
    fecha_alta = models.DateField("Fecha de alta", auto_now_add=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Negocio"
        verbose_name_plural = "Negocios"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    negocio = models.ForeignKey(
        Negocio,
        on_delete=models.PROTECT,
        related_name="usuarios",
        null=True,
        blank=True,
        verbose_name="Negocio",
        help_text="Negocio al que pertenece este usuario. Los superusuarios pueden no tener uno asignado.",
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"


class TenantOwnedModel(models.Model):
    negocio = models.ForeignKey(
        Negocio,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Negocio",
        editable=False,
    )
    creado_en = models.DateTimeField("Creado", auto_now_add=True)
    actualizado_en = models.DateTimeField("Actualizado", auto_now=True)

    objects = TenantManager()

    class Meta:
        abstract = True
