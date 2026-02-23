from django.db import models
from django.contrib.auth.models import User
import uuid


# ----------------------------------------
# جدول الملاعب (Pitches)
# ----------------------------------------
class Pitch(models.Model):
    is_new = models.BooleanField(default=False, verbose_name="ملعب جديد؟")
    is_available = models.BooleanField(default=True, verbose_name="متاح الآن؟")
    SIZE_CHOICES = [
        ('5x5', 'خماسي (5 ضد 5)'),
        ('7x7', 'سباعي (7 ضد 7)'),
        ('11x11', 'قانوني (11 ضد 11)'),
    ]

    FLOOR_CHOICES = [
        ('Artificial', 'نجيل صناعي'),
        ('Natural', 'نجيل طبيعي'),
        ('Tartan', 'ترتان / مطاط'),
    ]

    LOCATION_CHOICES = [
        ('Abbaseya', 'العباسية'),
        ('Nasr City', 'مدينة نصر'),
        ('New Cairo', 'مصر الجديدة'),
        ('Maadi', 'المعادي'),
        ('Shoubra', 'شبرا'),
        ('Dokki', 'الدقي'),
        ('Giza', 'الجيزة'),
        ('Zamalek', 'الزمالك'),
        ('Haram', 'الهرم'),
        ('Faisal', 'فيصل'),
        ('Obour', 'العبور'),
        ('Shorouk', 'الشروق'),
        ('October', '6 أكتوبر'),
        ('Sheikh Zayed', 'الشيخ زايد'),
        ('Helwan', 'حلوان'),
        ('Mokattam', 'المقطم'),
    ]

    name            = models.CharField(max_length=100, verbose_name="اسم الملعب")
    price_per_hour  = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر الساعة الأساسي")
    location        = models.CharField(max_length=50, choices=LOCATION_CHOICES, default='Nasr City', verbose_name="المنطقة")
    address         = models.CharField(max_length=255, blank=True, verbose_name="العنوان بالتفصيل")
    image           = models.ImageField(upload_to='pitch_images/', blank=True, null=True, verbose_name="صورة الملعب")
    google_map_link = models.URLField(blank=True, null=True, verbose_name="رابط جوجل ماب")
    description     = models.TextField(blank=True, verbose_name="وصف ومميزات الملعب")
    phone_number    = models.CharField(max_length=15, blank=True, verbose_name="رقم الملعب")
    owner_name      = models.CharField(max_length=100, blank=True, verbose_name="اسم صاحب الملعب")
    latitude        = models.FloatField(blank=True, null=True, verbose_name="خط العرض (Latitude)")
    longitude       = models.FloatField(blank=True, null=True, verbose_name="خط الطول (Longitude)")
    size            = models.CharField(max_length=10, choices=SIZE_CHOICES, default='5x5', verbose_name="حجم الملعب")
    floor_type      = models.CharField(max_length=20, choices=FLOOR_CHOICES, default='Artificial', verbose_name="نوع الأرضية")
    has_showers     = models.BooleanField(default=False, verbose_name="يوجد حمامات/دش")
    has_parking     = models.BooleanField(default=False, verbose_name="يوجد جراج")
    has_ball        = models.BooleanField(default=True,  verbose_name="توفر كرة")
    has_bibs        = models.BooleanField(default=False, verbose_name="توفر ماركرات (صديري)")

    class Meta:
        verbose_name        = "ملعب"
        verbose_name_plural = "الملاعب"

    def __str__(self):
        return f"{self.name} ({self.get_location_display()})"


# ----------------------------------------
# جدول أسعار خاصة
# ----------------------------------------
class PitchPricing(models.Model):
    pitch         = models.ForeignKey(Pitch, on_delete=models.CASCADE, verbose_name="الملعب")
    specific_date = models.DateField(null=True, blank=True, verbose_name="تاريخ معين (اختياري)")
    start_hour    = models.IntegerField(default=0,  verbose_name="من الساعة")
    end_hour      = models.IntegerField(default=24, verbose_name="إلى الساعة")
    price         = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="السعر الخاص")

    class Meta:
        verbose_name        = "سعر خاص / خصم"
        verbose_name_plural = "قائمة الأسعار الخاصة"

    def __str__(self):
        date_info = f"يوم {self.specific_date}" if self.specific_date else "كل الأيام"
        return f"{self.pitch.name} - {date_info} ({self.start_hour}:00 → {self.end_hour}:00) بـ {self.price}"


# ----------------------------------------
# جدول الحجوزات (Bookings)
# ----------------------------------------
class Booking(models.Model):
    STATUS_CHOICES = [
        ('Pending',   'قيد المراجعة (انتظار التأكيد)'),
        ('Confirmed', 'تم التأكيد'),
        ('Cancelled', 'ملغي / مرفوض'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('Full',       'دفع كامل'),
        ('Deposit',    'دفع عربون (50 ج.م)'),
        ('PayAtPitch', 'دفع في الملعب (للمميزين فقط)'),
    ]

    pitch        = models.ForeignKey(Pitch, on_delete=models.CASCADE, verbose_name="الملعب")
    user         = models.ForeignKey(User,  on_delete=models.CASCADE, verbose_name="المستخدم")
    date         = models.DateField(verbose_name="تاريخ الحجز")
    time         = models.CharField(max_length=10, verbose_name="وقت الحجز")
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', verbose_name="الحالة")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='Full', verbose_name="نوع الدفع")
    created_at   = models.DateTimeField(auto_now_add=True, verbose_name="وقت إنشاء الطلب")
    booking_code = models.CharField(max_length=10, unique=True, editable=False, null=True, verbose_name="كود الحجز")

    class Meta:
        verbose_name        = "حجز"
        verbose_name_plural = "الحجوزات"
        ordering            = ['-date', '-time']

    def save(self, *args, **kwargs):
        if not self.booking_code:
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
        ('Cash',     'دفع في الملعب'),
        ('Fawry',    'فوري'),
    ]

    booking        = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment_details', verbose_name="الحجز المرتبط")
    transaction_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="رقم العملية / التحويل")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='Cash', verbose_name="طريقة الدفع")
    is_verified    = models.BooleanField(default=False, verbose_name="تم التحقق من الدفع؟")
    timestamp      = models.DateTimeField(auto_now_add=True, verbose_name="وقت الدفع")

    class Meta:
        verbose_name        = "عملية دفع"
        verbose_name_plural = "المدفوعات"

    def __str__(self):
        return f"دفع للكود {self.booking.booking_code} - {self.get_payment_method_display()}"


# ----------------------------------------
# جدول التقييمات (Reviews)
# ----------------------------------------
class Review(models.Model):
    pitch      = models.ForeignKey(Pitch, related_name='reviews', on_delete=models.CASCADE, verbose_name="الملعب")
    user       = models.ForeignKey(User,  on_delete=models.CASCADE, verbose_name="المستخدم")
    rating     = models.IntegerField(default=5, verbose_name="التقييم (من 5)")
    comment    = models.TextField(blank=True, null=True, verbose_name="التعليق")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "تقييم"
        verbose_name_plural = "التقييمات"
        ordering            = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.pitch.name} ({self.rating}★)"