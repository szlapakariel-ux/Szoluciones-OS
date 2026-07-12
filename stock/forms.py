from django import forms

from .models import TipoProducto, UnidadMedida


class EditarProductosMasivoForm(forms.Form):
    """Todos los campos son opcionales: dejar en blanco = no tocar ese campo.
    Solo se aplican a los productos seleccionados los campos que se completen."""

    activo = forms.ChoiceField(
        label="Activo",
        required=False,
        choices=[("", "— sin cambios —"), ("true", "Sí"), ("false", "No")],
    )
    tipo = forms.ChoiceField(
        label="Tipo",
        required=False,
        choices=[("", "— sin cambios —")] + list(TipoProducto.choices),
    )
    unidad_medida = forms.ChoiceField(
        label="Unidad de medida",
        required=False,
        choices=[("", "— sin cambios —")] + list(UnidadMedida.choices),
    )
    precio_venta = forms.DecimalField(label="Precio de venta", required=False, max_digits=12, decimal_places=2)
    costo = forms.DecimalField(label="Costo", required=False, max_digits=12, decimal_places=2)
    stock_minimo = forms.DecimalField(label="Stock mínimo", required=False, max_digits=12, decimal_places=2)
    porciones_por_unidad = forms.IntegerField(label="Porciones por unidad", required=False, min_value=1)
    cantidad_minima_mayorista = forms.IntegerField(label="Cantidad mínima por mayor", required=False, min_value=1)
    precio_mayorista = forms.DecimalField(label="Precio por mayor", required=False, max_digits=12, decimal_places=2)

    def campos_a_actualizar(self):
        datos = self.cleaned_data
        cambios = {}
        if datos.get("activo"):
            cambios["activo"] = datos["activo"] == "true"
        for campo in (
            "tipo", "unidad_medida", "precio_venta", "costo", "stock_minimo",
            "porciones_por_unidad", "cantidad_minima_mayorista", "precio_mayorista",
        ):
            valor = datos.get(campo)
            if valor not in (None, ""):
                cambios[campo] = valor
        return cambios
