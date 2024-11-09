from django.http import JsonResponse
from django.db.models import Q
from products.models import Product
import json
from django.views.decorators.http import require_http_methods

def search_products(request):
    term = request.GET.get('term', '').strip()
    print(f"Término de búsqueda: {term}")

    if len(term) < 2:
        return JsonResponse([], safe=False)

    # Usando contains en lugar de LIKE
    products = Product.objects.filter(
        Q(name__icontains=term) | Q(brand__icontains=term),
        is_active=True,
        stock__gt=0
    ).order_by('name')  # Ordenamos por nombre

    # Debug - Imprimir todos los productos activos
    print("\nTodos los productos activos:")
    all_products = Product.objects.filter(is_active=True)
    for p in all_products:
        print(f"- {p.name} (Marca: {p.brand}, Activo: {p.is_active}, Stock: {p.stock})")

    # Convertimos a lista y preparamos para JSON
    product_list = []
    for product in products:
        product_list.append({
            'id': product.id,
            'name': product.name,
            'brand': product.brand if product.brand else '',
            'stock': product.stock,
            'sale_price': int(product.sale_price) if product.sale_price else 0
        })

    print(f"Productos encontrados: {product_list}")
    return JsonResponse(product_list, safe=False)

def add_to_cart(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))

        product = Product.objects.get(id=product_id)
        
        if quantity > product.stock:
            return JsonResponse({
                'error': f'Stock insuficiente. Stock disponible: {product.stock}'
            }, status=400)

        # Obtener o inicializar el carrito
        cart = request.session.get('cart', [])
        
        # Buscar si el producto ya está en el carrito
        found = False
        for item in cart:
            if item['product_id'] == product_id:
                new_quantity = item['quantity'] + quantity
                if new_quantity > product.stock:
                    return JsonResponse({
                        'error': f'Stock insuficiente. Stock disponible: {product.stock}'
                    }, status=400)
                item['quantity'] = new_quantity
                found = True
                break

        if not found:
            cart.append({
                'product_id': product_id,
                'name': product.name,
                'quantity': quantity,
                'price': product.sale_price
            })

        request.session['cart'] = cart
        
        return JsonResponse({
            'success': True,
            'cart': cart,
            'total': sum(item['price'] * item['quantity'] for item in cart)
        })

    except Product.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def update_cart(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))

        if quantity < 1:
            return JsonResponse({'error': 'La cantidad debe ser mayor a 0'}, status=400)

        # Verificar stock disponible
        product = Product.objects.get(id=product_id)
        if quantity > product.stock:
            return JsonResponse({
                'error': f'Stock insuficiente. Stock disponible: {product.stock}'
            }, status=400)

        # Actualizar cantidad en el carrito
        cart = request.session.get('cart', [])
        
        for item in cart:
            if item['product_id'] == product_id:
                item['quantity'] = quantity
                break

        request.session['cart'] = cart
        
        return JsonResponse({
            'success': True,
            'cart': cart,
            'total': sum(item['price'] * item['quantity'] for item in cart)
        })

    except Product.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def remove_from_cart(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    cart = request.session.get('cart', [])
    cart = [item for item in cart if item['product_id'] != product_id]
    request.session['cart'] = cart
    
    return JsonResponse({
        'success': True,
        'cart': cart,
        'total': sum(item['price'] * item['quantity'] for item in cart)
    })

@require_http_methods(["POST"])
def init_cart(request):
    try:
        data = json.loads(request.body)
        cart = data.get('cart', [])
        request.session['cart'] = cart
        return JsonResponse({'success': True, 'cart': cart})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)