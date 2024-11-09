from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import Sale, SaleDetail
from products.models import Product
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import transaction
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json

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
    fields = ['status']  
    template_name = 'sales/detail.html' 
    http_method_names = ['post']

    @transaction.atomic
    def form_valid(self, form):
        print("\n=== DEBUG UPDATE STATUS ===")
        sale = form.save(commit=False)
        old_status = Sale.objects.get(pk=sale.pk).status
        new_status = form.cleaned_data['status']
        
        print(f"Venta #{sale.pk}")
        print(f"Estado anterior: {old_status}")
        print(f"Nuevo estado: {new_status}")

        # Cambiar de PENDING a COMPLETED
        if old_status == 'PENDING' and new_status == 'COMPLETED' and not sale.is_stock_deducted:
            for detail in sale.saledetail_set.all():
                product = detail.product
                if product.stock < detail.quantity:
                    messages.error(self.request, f"No hay suficiente stock para {product.name}")
                    return redirect('sales:detail', pk=sale.pk)

                product.stock -= detail.quantity
                product.save()
            sale.is_stock_deducted = True
            print("Stock descontado")

        sale.save()
        print(f"Venta guardada. Estado final: {sale.status}")
        
        # Verificar que se guardó correctamente
        saved_sale = Sale.objects.get(pk=sale.pk)
        print(f"Estado en BD: {saved_sale.status}")
        
        messages.success(self.request, f'El estado de la venta ha sido actualizado a {new_status}.')
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
    
@method_decorator(csrf_exempt, name='dispatch')
class SaleEditView(LoginRequiredMixin, UpdateView):
    model = Sale
    template_name = 'sales/edit.html'
    fields = ['payment_method', 'status']

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Verificar si es una petición AJAX/JSON
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                cart = data.get('cart', [])
                payment_method = data.get('payment_method')
                status = data.get('status')

                if not cart:
                    return JsonResponse({'error': "No hay productos en la venta"}, status=400)

                # Restaurar stock anterior si ya fue descontado
                if self.object.is_stock_deducted:
                    for detail in self.object.saledetail_set.all():
                        product = detail.product
                        product.stock += detail.quantity
                        product.save()

                # Eliminar detalles anteriores
                self.object.saledetail_set.all().delete()

                # Actualizar la venta
                self.object.payment_method = payment_method
                self.object.status = status
                self.object.total = sum(item['price'] * item['quantity'] for item in cart)
                self.object.is_modified = True
                self.object.save()

                # Crear nuevos detalles y actualizar stock
                for item in cart:
                    product = Product.objects.get(id=item['product_id'])
                    
                    # Verificar stock disponible
                    if product.stock < item['quantity']:
                        raise ValidationError(f'Stock insuficiente para {product.name}')

                    # Descontar stock
                    product.stock -= item['quantity']
                    product.save()

                    # Crear detalle
                    SaleDetail.objects.create(
                        sale=self.object,
                        product=product,
                        quantity=item['quantity'],
                        unit_price=item['price'],
                        purchase_price=product.purchase_price,
                        is_tax_included=product.is_sale_with_tax,
                        subtotal=item['price'] * item['quantity']
                    )

                return JsonResponse({
                    'success': True,
                    'redirect_url': reverse('sales:detail', kwargs={'pk': self.object.pk})
                })

            except json.JSONDecodeError:
                return JsonResponse({'error': 'Datos inválidos'}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)
        
        # Si no es JSON, procesar como formulario normal
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Convertir los detalles de la venta a un formato serializable
        initial_cart = []
        for detail in self.object.saledetail_set.all():
            initial_cart.append({
                'product_id': detail.product.id,
                'name': detail.product.name,
                'quantity': detail.quantity,
                'price': detail.unit_price,
            })

        context.update({
            'products': Product.objects.filter(is_active=True),
            'payment_methods': Sale.PAYMENT_CHOICES,
            'sale_status': Sale.SALE_STATUS,
            'initial_cart': initial_cart
        })
        return context