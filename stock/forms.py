from django import forms

from unfold.widgets import UnfoldAdminDecimalFieldWidget, UnfoldAdminIntegerFieldWidget, UnfoldAdminSelectWidget

from .models import TipoProducto, UnidadMedida


class EditarProductosMasivoForm(forms.Form):
    """Todos los campos son opcionales: dejar en blanco = no tocar ese campo.
    Solo se aplican a los productos seleccionados los campos que se completen."""

    activo = forms.ChoiceField(
        label="Activo",
        required=False,
        choices=[("", "— sin cambios —"), ("true", "Sí"), ("false", "No")],
        widget=UnfoldAdminSelectWidget,
    )
    tipo = forms.ChoiceField(
        label="Tipo",
        required=False,
        choices=[("", "— sin cambios —")] + list(TipoProducto.choices),
        widget=UnfoldAdminSelectWidget,
    )
    unidad_medida = forms.ChoiceField(
        label="Unidad de medida",
        required=False,
        choices=[("", "— sin cambios —")] + list(UnidadMedida.choices),
        widget=UnfoldAdminSelectWidget,
    )
    precio_venta = forms.DecimalField(
        label="Precio de venta", required=False, max_digits=12, decimal_places=2,
        widget=UnfoldAdminDecimalFieldWidget,
    )
    costo = forms.DecimalField(
        label="Costo", required=False, max_digits=12, decimal_places=2,
        widget=UnfoldAdminDecimalFieldWidget,
    )
    stock_minimo = forms.DecimalField(
        label="Stock mínimo", required=False, max_digits=12, decimal_places=2,
        widget=UnfoldAdminDecimalFieldWidget,
    )
    porciones_por_unidad = forms.IntegerField(
        label="Porciones por unidad", required=False, min_value=1,
        widget=UnfoldAdminIntegerFieldWidget,
    )
    cantidad_minima_mayorista = forms.IntegerField(
        label="Cantidad mínima por mayor", required=False, min_value=1,
        widget=UnfoldAdminIntegerFieldWidget,
    )
    precio_mayorista = forms.DecimalField(
        label="Precio por mayor", required=False, max_digits=12, decimal_places=2,
        widget=UnfoldAdminDecimalFieldWidget,
    )

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
