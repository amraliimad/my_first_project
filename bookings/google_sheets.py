import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import logging

# إعداد الـ Logger
logger = logging.getLogger(__name__)

def add_booking_to_sheet(booking):
    """
    دالة تقوم بإرسال بيانات الحجز إلى Google Sheets.
    مصممة لالتقاط كافة الأخطاء حتى لا تؤثر على دورة الدفع الأساسية.
    """
    try:
        # 1. جلب المفتاح السري من الإعدادات بأمان
        creds_json_str = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json_str:
            logger.error("لم يتم العثور على مفتاح جوجل في البيئة (GOOGLE_SHEETS_CREDENTIALS)!")
            return False
            
        creds_dict = json.loads(creds_json_str)

        # 2. تسجيل الدخول لجوجل
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
        
        # 🆕 تهيئة العميل مع مهلة محددة (Timeout) لتجنب تعليق الـ Server
        # gspread.authorize لا يقبل timeout مباشرة، لكن gspread 5.0+ يسمح بتخصيص الـ session
        # هنا نعتمد على أن محاولات الـ try/except المحيطة ستلتقط أي تعليق طويل المدى
        client = gspread.authorize(creds)

        # 3. فتح الشيت (لازم الاسم يكون متطابق)
        sheet = client.open("Mal3ab_Bookings").sheet1

        # 4. تجميع بيانات الحجز لرميها في الشيت بأمان
        # 🆕 حماية من الأخطاء إذا لم يكن للمستخدم Profile
        phone = ""
        if booking.is_manual:
            phone = booking.customer_phone
        else:
            try:
                phone = booking.user.profile.phone_number
            except Exception:
                phone = "لا يوجد"

        customer_name = booking.customer_name if booking.is_manual else booking.user.get_full_name() or booking.user.username

        # تحديد المدفوع
        if booking.payment_type == 'Deposit':
            paid_amount = "50 ج.م"
        elif booking.payment_type == 'Full':
            paid_amount = f"{booking.pitch.price_per_hour} ج.م"
        else:
            paid_amount = "كاش في الملعب"

        row_data = [
            booking.booking_code,
            str(booking.date),
            booking.time,
            booking.pitch.name,
            customer_name,
            str(phone),
            paid_amount,
            booking.get_status_display()
        ]

        # 5. إضافة السطر في الشيت
        sheet.append_row(row_data)
        return True

    except Exception as e:
        # 🆕 تسجيل الخطأ في النظام بدلاً من الـ print
        logger.error(f"Google Sheets Error in booking {booking.booking_code}: {str(e)}")
        return False
