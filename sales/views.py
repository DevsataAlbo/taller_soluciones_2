from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Sale, SaleDetail
from users.mixins import AdminRequiredMixin
from products.models import Product
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import transaction
from django.core.exceptions import ValidationError

class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'sales/list.html'
    context_object_name = 'sales'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros
        date = self.request.GET.get('date')
        status = self.request.GET.get('status')
        payment_method = self.request.GET.get('payment_method')
        
        if date:
            queryset = queryset.filter(date__date=date)
        if status:
            queryset = queryset.filter(status=status)
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sale_status'] = Sale.SALE_STATUS
        context['payment_methods'] = Sale.PAYMENT_CHOICES
        return context

class SaleCreateView(LoginRequiredMixin, CreateView):
    model = Sale
    template_name = 'sales/create.html'
    fields = ['payment_method', 'status']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'products': Product.objects.filter(is_active=True, stock__gt=0),
            'payment_methods': Sale.PAYMENT_CHOICES,
            'sale_status': Sale.SALE_STATUS,
        })
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            cart = request.session.get('cart', [])
            if not cart:
                return JsonResponse({'error': "No hay productos en el carrito"}, status=400)

            total_venta = sum(item['price'] * item['quantity'] for item in cart)
            if total_venta == 0:
                return JsonResponse({'error': "El total de la venta no puede ser 0"}, status=400)

            sale = Sale(
                number=Sale.generate_sale_number(),
                payment_method=request.POST.get('payment_method'),
                status=request.POST.get('status'),
                user=request.user,
                total=total_venta,
                is_stock_deducted=True  # Stock descontado al crear la venta
            )
            sale.full_clean()
            sale.save()
            print("Venta guardada, ID de venta:", sale.pk)

            for item in cart:
                product = Product.objects.get(id=item['product_id'])

                # Verificación de stock disponible
                if product.stock < item['quantity']:
                    return JsonResponse({'error': f'Stock insuficiente para {product.name}'}, status=400)

                # Descuento del stock
                product.stock -= item['quantity']
                product.save()

                # Crear el detalle de la venta
                subtotal = item['price'] * item['quantity']
                SaleDetail.objects.create(
                    sale=sale,
                    product=product,
                    quantity=item['quantity'],
                    unit_price=item['price'],
                    purchase_price=product.purchase_price,
                    is_tax_included=product.is_sale_with_tax,
                    subtotal=subtotal
                )

            request.session['cart'] = []
            request.session.modified = True

            return JsonResponse({
                'success': True,
                'redirect_url': reverse_lazy('sales:detail', kwargs={'pk': sale.pk}).__str__()
            })

        except Product.DoesNotExist:
            return JsonResponse({'error': "Uno o más productos no existen"}, status=400)
        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            print("Error detallado:", str(e))
            return JsonResponse({'error': f"Error al procesar la venta: {str(e)}"}, status=500)


class SaleDetailView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = 'sales/detail.html'
    context_object_name = 'sale'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    

class SaleUpdateStatusView(LoginRequiredMixin, UpdateView):
    model = Sale
    fields = ['status', 'payment_method']
    http_method_names = ['post']

    @transaction.atomic
    def form_valid(self, form):
        sale = form.save(commit=False)
        
        old_status = Sale.objects.get(pk=sale.pk).status
        new_status = form.cleaned_data['status']

        # Si el estado cambia a "CANCELLED", restituir el stock
        if new_status == "CANCELLED" and sale.is_stock_deducted:
            for detail in sale.saledetail_set.all():
                product = detail.product
                product.stock += detail.quantity
                product.save()
            sale.is_stock_deducted = False  # Marcar como no descontado
            messages.success(self.request, f'Se ha anulado la venta y el stock ha sido restituido.')

        # Si el estado cambia de "PENDING" a "COMPLETED", descontar stock solo si no se ha descontado
        elif old_status == 'PENDING' and new_status == 'COMPLETED' and not sale.is_stock_deducted:
            for detail in sale.saledetail_set.all():
                product = detail.product
                if product.stock < detail.quantity:
                    messages.error(self.request, f"No hay suficiente stock para {product.name}")
                    return redirect('sales:detail', pk=sale.pk)
                
                product.stock -= detail.quantity
                product.save()
            sale.is_stock_deducted = True  # Marcar como descontado
            messages.success(self.request, f'Venta actualizada a {sale.get_status_display()}')

        sale.save()
        return redirect('sales:detail', pk=sale.pk)

class SaleCancelConfirmationView(LoginRequiredMixin, TemplateView):
    template_name = 'sales/cancel_confirmation.html'
    model = Sale

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale = Sale.objects.get(pk=self.kwargs['pk'])
        context['sale'] = sale
        return context

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        sale = Sale.objects.get(pk=self.kwargs['pk'])
        
        if sale.status == 'CANCELLED':
            messages.error(request, "Esta venta ya está cancelada.")
            return redirect('sales:detail', pk=sale.pk)
        
        # Restaurar el stock al cancelar la venta
        for detail in sale.saledetail_set.all():
            product = detail.product
            product.stock += detail.quantity
            product.save()

        # Actualizar el estado de la venta y marcar el stock como no descontado
        sale.status = 'CANCELLED'
        sale.is_stock_deducted = False
        sale.save()
        
        messages.success(request, "La venta ha sido cancelada y el stock ha sido restaurado.")
        return redirect('sales:detail', pk=sale.pk)