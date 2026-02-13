from django.db import models
from django.contrib.auth.models import User
import uuid  # مكتبة لتوليد أكواد عشوائية فريدة

# ----------------------------------------
# جدول الملاعب (Pitches)
# ----------------------------------------
# في ملف models.py

class Pitch(models.Model):
    # خيارات حجم الملعب
    SIZE_CHOICES = [
        ('5x5', 'خماسي (5 ضد 5)'),
        ('7x7', 'سباعي (7 ضد 7)'),
        ('11x11', 'قانوني (11 ضد 11)'),
    ]

    # خيارات نوع الأرضية
    FLOOR_CHOICES = [
        ('Artificial', 'نجيل صناعي'),
        ('Natural', 'نجيل طبيعي'),
        ('Tartan', 'ترتان / مطاط'),
    ]

    name = models.CharField(max_length=100, verbose_name="اسم الملعب")
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر الساعة")
    
    # --- إضافات جديدة ---
    image = models.ImageField(upload_to='pitch_images/', blank=True, null=True, verbose_name="صورة الملعب")
    location = models.CharField(max_length=200, blank=True, verbose_name="العنوان نصياً")
    google_map_link = models.URLField(blank=True, null=True, verbose_name="رابط جوجل ماب")
    description = models.TextField(blank=True, verbose_name="وصف ومميزات الملعب")
    phone_number = models.CharField(max_length=15, blank=True, verbose_name="رقم هاتف الحجز/الاستفسار")
    
    # تفاصيل فنية
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, default='5x5', verbose_name="حجم الملعب")
    floor_type = models.CharField(max_length=20, choices=FLOOR_CHOICES, default='Artificial', verbose_name="نوع الأرضية")
    
    # خدمات إضافية (True/False)
    has_showers = models.BooleanField(default=False, verbose_name="يوجد حمامات/دش")
    has_parking = models.BooleanField(default=False, verbose_name="يوجد جراج")
    has_ball = models.BooleanField(default=True, verbose_name="توفر كرة")
    has_bibs = models.BooleanField(default=False, verbose_name="توفر ماركرات (صديري)")

    class Meta:
        verbose_name = "ملعب"
        verbose_name_plural = "الملاعب"

    def __str__(self):
        return self.name

# ----------------------------------------
# جدول الحجوزات (Bookings)
# ----------------------------------------
class Booking(models.Model):
    # خيارات حالة الحجز
    STATUS_CHOICES = [
        ('Pending', 'قيد الانتظار (مطلوب)'),
        ('Confirmed', 'تم التأكيد'),
        ('Cancelled', 'ملغي'),
    ]

    # العلاقات والبيانات الأساسية
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE, verbose_name="الملعب")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="المستخدم")
    date = models.DateField(verbose_name="تاريخ الحجز")
    time = models.CharField(max_length=10, verbose_name="وقت الحجز")  # يخزن الساعة مثل "18:00"
    
    # حالة الحجز وتاريخ الإنشاء
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', verbose_name="الحالة")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="وقت إنشاء الطلب")
    
    # كود الحجز (الإيصال)
    booking_code = models.CharField(max_length=10, unique=True, editable=False, null=True, verbose_name="كود الحجز")

    class Meta:
        verbose_name = "حجز"
        verbose_name_plural = "الحجوزات"
        ordering = ['-date', '-time']  # ترتيب الحجوزات من الأحدث للأقدم

    def save(self, *args, **kwargs):
        # توليد كود حجز تلقائي إذا لم يكن موجوداً
        if not self.booking_code:
            # نولد كود طويل ونأخذ أول 8 حروف ونحولها لأحرف كبيرة
            self.booking_code = str(uuid.uuid4()).upper()[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.pitch.name} ({self.date})"


# ----------------------------------------
# جدول المدفوعات (Payments)
# ----------------------------------------
class Payment(models.Model):
    PAYMENT_METHODS = [
        ('Vodafone', 'فودافون كاش'),
        ('Instapay', 'إنستا باي'),
        ('Cash', 'دفع في الملعب'),
    ]

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment_details', verbose_name="الحجز المرتبط")
    transaction_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="رقم العملية / التحويل")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='Cash', verbose_name="طريقة الدفع")
    is_verified = models.BooleanField(default=False, verbose_name="تم التحقق من الدفع؟")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="وقت الدفع")

    class Meta:
        verbose_name = "عملية دفع"
        verbose_name_plural = "المدفوعات"

    def __str__(self):
        return f"دفع للكود {self.booking.booking_code} - {self.get_payment_method_display()}"