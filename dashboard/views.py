# views.py
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone
from sales.models import Sale, SaleDetail
from products.models import Product
from django.db.models import Sum, Count, F, ExpressionWrapper, FloatField
from django.db.models.functions import Cast

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener la fecha actual
        now = timezone.now()
        
        # 1. Total ventas por período
        context['sales_summary'] = {
            'day': Sale.objects.filter(
                date__date=now.date(),
                status='COMPLETED'
            ).aggregate(total=Sum('total'))['total'] or 0,
            
            'week': Sale.objects.filter(
                date__date__gte=now.date() - timezone.timedelta(days=7),
                status='COMPLETED'
            ).aggregate(total=Sum('total'))['total'] or 0,
            
            'month': Sale.objects.filter(
                date__year=now.year,
                date__month=now.month,
                status='COMPLETED'
            ).aggregate(total=Sum('total'))['total'] or 0,
            
            'year': Sale.objects.filter(
                date__year=now.year,
                status='COMPLETED'
            ).aggregate(total=Sum('total'))['total'] or 0,
        }
        
        # 2. Producto más vendido por período
        context['top_products'] = {
            'day': SaleDetail.objects.filter(
                sale__date__date=now.date(),
                sale__status='COMPLETED'
            ).values('product__name').annotate(
                total_quantity=Sum('quantity')
            ).order_by('-total_quantity').first(),
            
            'week': SaleDetail.objects.filter(
                sale__date__date__gte=now.date() - timezone.timedelta(days=7),
                sale__status='COMPLETED'
            ).values('product__name').annotate(
                total_quantity=Sum('quantity')
            ).order_by('-total_quantity').first(),
            
            'month': SaleDetail.objects.filter(
                sale__date__year=now.year,
                sale__date__month=now.month,
                sale__status='COMPLETED'
            ).values('product__name').annotate(
                total_quantity=Sum('quantity')
            ).order_by('-total_quantity').first(),
            
            'year': SaleDetail.objects.filter(
                sale__date__year=now.year,
                sale__status='COMPLETED'
            ).values('product__name').annotate(
                total_quantity=Sum('quantity')
            ).order_by('-total_quantity').first(),
        }
        
        # 3. Top 5 productos con mejor rentabilidad
        context['top_profitable_products'] = SaleDetail.objects.filter(
            sale__status='COMPLETED'
        ).values('product__name').annotate(
            total_profit=Sum(
                (F('unit_price') - F('purchase_price')) * F('quantity')
            )
        ).order_by('-total_profit')[:5]

        # 4. Top 5 productos con stock más bajo (que estén activos)
        context['low_stock_products'] = Product.objects.filter(
            is_active=True,
            stock__gt=0  # Solo productos con stock mayor a 0
        ).order_by('stock')[:5]

        return context