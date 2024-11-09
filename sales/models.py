from django.db import models
from django.contrib.auth import get_user_model
from products.models import Product
from django.core.exceptions import ValidationError

class Sale(models.Model):
    PAYMENT_CHOICES = [
        ('CASH', 'Efectivo'),
        ('TRANSFER', 'Transferencia'),
        ('DEBIT', 'Tarjeta Débito'),
        ('CREDIT', 'Tarjeta Crédito'),
    ]

    SALE_STATUS = [
        ('COMPLETED', 'Completada'),
        ('PENDING', 'Pendiente de Pago'),
        ('CANCELLED', 'Anulada'),
    ]

    number = models.CharField(max_length=10, unique=True, verbose_name="Número de venta")
    date = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y hora")
    payment_method = models.CharField(
        max_length=10, 
        choices=PAYMENT_CHOICES,
        verbose_name="Método de pago"
    )
    total = models.IntegerField(default=0, verbose_name="Total")
    status = models.CharField(
        max_length=10,
        choices=SALE_STATUS,
        default='COMPLETED',
        verbose_name="Estado"
    )
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.PROTECT,
        verbose_name="Usuario"
    )
    is_stock_deducted = models.BooleanField(default=False, verbose_name="Stock descontado")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    is_modified = models.BooleanField(default=False, verbose_name="Modificada")

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-date']

    def __str__(self):
        return f"Venta #{self.number}"

    def get_total_items(self):
        return self.saledetail_set.count()

    def calculate_total(self):
        return sum(detail.subtotal for detail in self.saledetail_set.all())

    def calculate_profit(self):
        """Calcula la ganancia total de la venta"""
        return sum(detail.calculate_profit() for detail in self.saledetail_set.all())

    @staticmethod
    def generate_sale_number():
        """Genera un número único para la venta"""
        last_sale = Sale.objects.all().order_by('id').last()
        if not last_sale:
            return 'VTA-00001'
        sale_number = last_sale.number
        sale_int = int(sale_number.split('-')[1])
        new_sale_int = sale_int + 1
        return f'VTA-{str(new_sale_int).zfill(5)}'

    def clean(self):
        """Validaciones del modelo"""
        if self.status == 'COMPLETED' and self.total == 0:
            raise ValidationError("No se puede completar una venta sin productos")

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self.generate_sale_number()
        self.clean()  # Valida condiciones básicas sin dependencia de saledetail_set
        super().save(*args, **kwargs)

    def mark_as_modified(self):
        self.is_modified = True
        self.save()

class SaleDetail(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, verbose_name="Venta")
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT, 
        verbose_name="Producto"
    )
    quantity = models.IntegerField(verbose_name="Cantidad")
    unit_price = models.IntegerField(verbose_name="Precio unitario")
    purchase_price = models.IntegerField(verbose_name="Precio de compra")
    subtotal = models.IntegerField(verbose_name="Subtotal")
    is_tax_included = models.BooleanField(default=True, verbose_name="Incluye IVA")

    class Meta:
        verbose_name = "Detalle de venta"
        verbose_name_plural = "Detalles de venta"

    def __str__(self):
        return f"{self.product.name} - {self.quantity} unidades"

    def calculate_profit(self):
        """Calcula la ganancia de esta línea de venta"""
        sale_price_net = self.unit_price / 1.19 if self.is_tax_included else self.unit_price
        purchase_price_net = self.purchase_price / 1.19 if self.product.is_purchase_with_tax else self.purchase_price
        return int((sale_price_net - purchase_price_net) * self.quantity)

    def save(self, *args, **kwargs):
        # Calcula el subtotal antes de guardar
        self.subtotal = self.quantity * self.unit_price
        super().save(*args, **kwargs)

        # Revisar que la venta ya exista en la base de datos antes de actualizar el total
        if self.sale.pk:
            self.sale.total = self.sale.calculate_total()
            self.sale.save()
