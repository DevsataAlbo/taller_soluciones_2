from django.db import models
from django.urls import reverse

class Category(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nombre")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nombre")
    brand = models.CharField(max_length=100, verbose_name="Marca")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name="Categoría")
    description = models.TextField(verbose_name="Descripción", blank=True)
    purchase_price = models.IntegerField(verbose_name="Precio de compra")
    is_purchase_with_tax = models.BooleanField(default=True, verbose_name="Precio de compra incluye IVA")
    sale_price = models.IntegerField(verbose_name="Precio de venta")
    is_sale_with_tax = models.BooleanField(default=True, verbose_name="Precio de venta incluye IVA")
    stock = models.IntegerField(default=0, verbose_name="Stock")
    image = models.ImageField(upload_to='products/', verbose_name="Imagen", null=True, blank=True)
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    def get_purchase_price_without_tax(self):
        """Retorna el precio de compra sin IVA"""
        if self.is_purchase_with_tax:
            return int(self.purchase_price / 1.19)
        return self.purchase_price

    def get_sale_price_without_tax(self):
        """Retorna el precio de venta sin IVA"""
        if self.is_sale_with_tax:
            return int(self.sale_price / 1.19)
        return self.sale_price

    def calculate_profit_percentage(self):
        """Calcula el porcentaje de ganancia basado en precios netos"""
        purchase_net = self.get_purchase_price_without_tax()
        sale_net = self.get_sale_price_without_tax()
        
        if purchase_net > 0:
            profit = ((sale_net - purchase_net) / purchase_net) * 100
            return int(profit)
        return 0

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['-created']

    def __str__(self):
        return self.name