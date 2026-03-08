import requests
import logging
from django.conf import settings

# إعداد الـ Logger لتسجيل الأخطاء المالية بدقة
logger = logging.getLogger(__name__)

PAYMOB_BASE_URL = "https://accept.paymob.com/api"

def paymob_auth():
    """الخطوة 1: الحصول على Auth Token من Paymob"""
    try:
        response = requests.post(f"{PAYMOB_BASE_URL}/auth/tokens", json={
            "api_key": settings.PAYMOB_API_KEY
        }, timeout=10) # 🆕 إضافة Timeout لمنع تعليق السيرفر
        response.raise_for_status() # 🆕 التحقق من نجاح الطلب
        return response.json().get("token")
    except Exception as e:
        logger.error(f"Paymob Auth Error: {str(e)} - {response.text if 'response' in locals() else ''}")
        raise Exception("فشل الاتصال ببوابة الدفع. يرجى المحاولة لاحقاً.")


def create_order(auth_token, amount_cents, booking_code):
    """الخطوة 2: إنشاء Order على Paymob"""
    try:
        response = requests.post(f"{PAYMOB_BASE_URL}/ecommerce/orders", json={
            "auth_token": auth_token,
            "delivery_needed": "false",
            "amount_cents": str(amount_cents),
            "currency": "EGP",
            "merchant_order_id": booking_code,
            "items": []
        }, timeout=10)
        response.raise_for_status()
        return response.json().get("id")
    except Exception as e:
        logger.error(f"Paymob Order Error: {str(e)} - {response.text if 'response' in locals() else ''}")
        raise Exception("فشل في إنشاء طلب الدفع.")


def create_payment_key(auth_token, order_id, amount_cents, user, phone):
    """الخطوة 3: إنشاء Payment Key"""
    try:
        # Paymob يرفض الأسماء التي تحتوي على رموز أو تكون فارغة تماماً
        first_name = user.first_name.strip() if user.first_name else "User"
        last_name = user.last_name.strip() if user.last_name else "Name"
        # يجب تمرير الهاتف بصيغة صحيحة (وقد تم حمايته في forms.py بالفعل)

        response = requests.post(f"{PAYMOB_BASE_URL}/acceptance/payment_keys", json={
            "auth_token": auth_token,
            "amount_cents": str(amount_cents),
            "expiration": 3600,
            "order_id": str(order_id),
            "billing_data": {
                "first_name": first_name,
                "last_name": last_name,
                "email": user.email or "no-reply@mal3abonline.com",
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
        }, timeout=10)
        response.raise_for_status()
        return response.json().get("token")
    except Exception as e:
        logger.error(f"Paymob Payment Key Error: {str(e)} - {response.text if 'response' in locals() else ''}")
        raise Exception("بيانات العميل غير مقبولة لدى بوابة الدفع، تأكد من صحة رقم الهاتف.")


def pay_with_wallet(payment_key, phone):
    """الخطوة 4: الدفع بالمحفظة - يوجه المستخدم لصفحة الدفع"""
    try:
        response = requests.post(
            f"{PAYMOB_BASE_URL}/acceptance/payments/pay",
            json={
                "source": {
                    "identifier": phone,
                    "subtype": "WALLET"
                },
                "payment_token": payment_key
            }, timeout=15 # Wallet API أحياناً تتأخر قليلاً
        )
        response.raise_for_status()
        data = response.json()
        redirect_url = data.get("redirect_url")
        iframe_redirection_url = data.get("iframe_redirection_url")
        return redirect_url or iframe_redirection_url
    except Exception as e:
        logger.error(f"Paymob Wallet Request Error: {str(e)} - {response.text if 'response' in locals() else ''}")
        raise Exception("فشلت عملية توجيه المحفظة الإلكترونية.")
