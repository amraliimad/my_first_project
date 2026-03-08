import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

def add_booking_to_sheet(booking):
    try:
        # 1. جلب المفتاح السري من الإعدادات بأمان
        creds_json_str = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_json_str:
            print("لم يتم العثور على مفتاح جوجل!")
            return False
            
        creds_dict = json.loads(creds_json_str)

        # 2. تسجيل الدخول لجوجل
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scopes)
        client = gspread.authorize(creds)

        # 3. فتح الشيت (لازم الاسم يكون متطابق)
        sheet = client.open("Mal3ab_Bookings").sheet1

        # 4. تجميع بيانات الحجز لرميها في الشيت
        phone = booking.customer_phone if booking.is_manual else booking.user.profile.phone_number
        customer_name = booking.customer_name if booking.is_manual else booking.user.username

        # تحديد المدفوع
        if booking.payment_type == 'Deposit':
            paid_amount = "50 ج.م"
        elif booking.payment_type == 'Full':
            paid_amount = str(booking.pitch.price_per_hour) + " ج.م"
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
        print(f"Google Sheets Error: {e}")
        return False
