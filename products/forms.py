from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'brand', 'category', 'description', 'purchase_price', 
                 'is_purchase_with_tax', 'sale_price', 'is_sale_with_tax', 
                 'stock', 'image', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplicar clases de Tailwind a todos los campos
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.Select)):
                field.widget.attrs['class'] = 'w-full rounded-lg border-gray-300 focus:border-blue-500 focus:ring-blue-500'
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'w-full rounded-lg border-gray-300 focus:border-blue-500 focus:ring-blue-500'
                field.widget.attrs['rows'] = 3
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'rounded border-gray-300 text-blue-600 focus:ring-blue-500'

    def clean(self):
        cleaned_data = super().clean()
        purchase_price = cleaned_data.get('purchase_price')
        sale_price = cleaned_data.get('sale_price')
        is_purchase_with_tax = cleaned_data.get('is_purchase_with_tax')
        is_sale_with_tax = cleaned_data.get('is_sale_with_tax')

        # Convertir precios a neto si incluyen IVA
        purchase_net = int(purchase_price / 1.19) if is_purchase_with_tax else purchase_price
        sale_net = int(sale_price / 1.19) if is_sale_with_tax else sale_price

        if purchase_net and sale_net and sale_net <= purchase_net:
            raise forms.ValidationError(
                "El precio de venta neto debe ser mayor al precio de compra neto."
            )

        return cleaned_data