import threading

from django.db import models

_thread_locals = threading.local()


def set_current_business(negocio):
    _thread_locals.negocio = negocio


def get_current_business():
    return getattr(_thread_locals, "negocio", None)


def clear_current_business():
    if hasattr(_thread_locals, "negocio"):
        del _thread_locals.negocio


class TenantManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset()
        negocio = get_current_business()
        if negocio is not None:
            return qs.filter(negocio=negocio)
        return qs

    def all_tenants(self):
        return super().get_queryset()
