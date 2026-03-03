import requests
from django.conf import settings


PAYMOB_BASE_URL = "https://accept.paymob.com/api"


def paymob_auth():
    """الخطوة 1: الحصول على Auth Token من Paymob"""
    response = requests.post(f"{PAYMOB_BASE_URL}/auth/tokens", json={
        "api_key": settings.PAYMOB_API_KEY
    })
    return response.json().get("token")


def create_order(auth_token, amount_cents, booking_code):
    """الخطوة 2: إنشاء Order على Paymob"""
    response = requests.post(f"{PAYMOB_BASE_URL}/ecommerce/orders", json={
        "auth_token": auth_token,
        "delivery_needed": "false",
        "amount_cents": str(amount_cents),
        "currency": "EGP",
        "merchant_order_id": booking_code,
        "items": []
    })
    return response.json().get("id")


def create_payment_key(auth_token, order_id, amount_cents, user, phone):
    """الخطوة 3: إنشاء Payment Key"""
    response = requests.post(f"{PAYMOB_BASE_URL}/acceptance/payment_keys", json={
        "auth_token": auth_token,
        "amount_cents": str(amount_cents),
        "expiration": 3600,
        "order_id": str(order_id),
        "billing_data": {
            "first_name": user.first_name or user.username,
            "last_name": user.last_name or "N/A",
            "email": user.email or "test@test.com",
            "phone_number": phone,
            "apartment": "N/A",
            "floor": "N/A",
            "street": "N/A",
            "building": "N/A",
            "shipping_method": "N/A",
            "postal_code": "N/A",
            "city": "N/A",
            "country": "EG",
            "state": "N/A"
        },
        "currency": "EGP",
        "integration_id": int(settings.PAYMOB_INTEGRATION_ID_WALLET),
    })
    return response.json().get("token")


def pay_with_wallet(payment_key, phone):
    """الخطوة 4: الدفع بالمحفظة - يوجه المستخدم لصفحة الدفع"""
    response = requests.post(
        f"{PAYMOB_BASE_URL}/acceptance/payments/pay",
        json={
            "source": {
                "identifier": phone,
                "subtype": "WALLET"
            },
            "payment_token": payment_key
        }
    )
    data = response.json()
    # Paymob يرجع redirect_url لصفحة دفع المحفظة
    redirect_url = data.get("redirect_url")
    iframe_redirection_url = data.get("iframe_redirection_url")
    return redirect_url or iframe_redirection_url