from django.shortcuts import render, get_object_or_404, redirect
from .models import Product, Cart, CartItem, Category, Order, OrderItem, ProductRating, Wishlist
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q, Avg
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from .stripe_utils import create_payment_intent

def product_list(request):
    query = request.GET.get('q')
    category_slug = request.GET.get('category')
    
    products = Product.objects.filter(available=True)
    
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
    
    # Annotate products with average rating
    products = products.annotate(avg_rating=Avg('ratings__rating'))
    
    categories = Category.objects.all()
    return render(request, 'product_list.html', {
        'products': products,
        'categories': categories,
        'selected_category': category_slug
    })

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, available=True)
    ratings = ProductRating.objects.filter(product=product)
    user_rating = None
    in_wishlist = False
    
    if request.user.is_authenticated:
        user_rating = ProductRating.objects.filter(product=product, user=request.user).first()
        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        in_wishlist = product in wishlist.products.all()
    
    return render(request, 'product_detail.html', {
        'product': product,
        'ratings': ratings,
        'user_rating': user_rating,
        'in_wishlist': in_wishlist
    })

@login_required
def add_rating(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        
        if rating:
            ProductRating.objects.update_or_create(
                product=product,
                user=request.user,
                defaults={
                    'rating': rating,
                    'comment': comment
                }
            )
            messages.success(request, 'Your rating has been saved.')
        else:
            messages.error(request, 'Please select a rating.')
    
    return redirect('product_detail', pk=product_id)

@login_required
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    
    if product in wishlist.products.all():
        wishlist.products.remove(product)
        added = False
    else:
        wishlist.products.add(product)
        added = True
    
    return JsonResponse({'added': added})

@login_required
def wishlist(request):
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)
    products = wishlist.products.filter(available=True)
    return render(request, 'wishlist.html', {'products': products})

@login_required
def cart_detail(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    items = CartItem.objects.filter(cart=cart)
    total = sum(item.product.price * item.quantity for item in items)
    return render(request, 'cart_detail.html', {'cart_items': items, 'total': total})

@login_required
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    item.quantity += 1
    item.save()
    return redirect('cart_detail')

@login_required
def cart_remove(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = Cart.objects.get(user=request.user)
    CartItem.objects.filter(cart=cart, product=product).delete()
    return redirect('cart_detail')

@login_required
def checkout(request):
    cart = Cart.objects.get(user=request.user)
    cart_items = CartItem.objects.filter(cart=cart)

    total = sum(item.product.price * item.quantity for item in cart_items)

    if request.method == 'POST':
        # Create the order first
        order = Order.objects.create(
            user=request.user,
            status='Pending',
            total=total,
            created_at=timezone.now(),
            updated_at=timezone.now()
        )

        # Add items to the order
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                price=item.product.price,
                quantity=item.quantity
            )

        # Create Stripe payment intent
        intent = create_payment_intent(total)
        if intent:            
            return render(request, 'checkout.html', {
                'order': order,
                'client_secret': intent.client_secret,
                'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
            })
        else:
            messages.error(request, 'There was an error processing your payment. Please try again.')
            return redirect('cart_detail')

    # For GET request, just show the checkout form
    return render(request, 'checkout.html', {
        'cart_items': cart_items,
        'total': total,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    })

@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.status = 'Processing'
    order.save()
    
    # Clear the cart
    CartItem.objects.filter(cart__user=request.user).delete()
    
    messages.success(request, 'Your payment was successful!')
    return render(request, 'checkout.html', {'order': order})

@login_required
def payment_cancel(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.status = 'Cancelled'
    order.save()
    
    messages.warning(request, 'Your payment was cancelled.')
    return redirect('cart_detail')

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')  # Redirect to login after registration
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})
