import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_payment_intent(amount):
    """
    Create a Stripe PaymentIntent for the given amount
    """
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency='usd',
            automatic_payment_methods={
                'enabled': True,
            },
        )
        return intent
    except stripe.error.StripeError as e:
        print('Stripe Error:', e)
        return None 
    
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # 🔥 Handle the event
    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        print("✅ Payment succeeded:", intent['id'])

        # Update order/payment status in DB here

    elif event['type'] == 'payment_intent.payment_failed':
        intent = event['data']['object']
        print("❌ Payment failed:", intent['id'])

        # Handle failure logic

    return HttpResponse(status=200)
    
def check_payment_status(payment_intent_id):
    """
    Retrieve the PaymentIntent by ID and check its status
    """
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return intent['status']
    except stripe.error.StripeError as e:
        print('Stripe Error:', e)
        return None