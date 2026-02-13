from django.db import models
from django.contrib.auth.models import User
import uuid  # مكتبة لتوليد أكواد عشوائية فريدة

# ----------------------------------------
# جدول الملاعب (Pitches)
# ----------------------------------------
class Pitch(models.Model):
    name = models.CharField(max_length=100, verbose_name="اسم الملعب")
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر الساعة")
    # يمكنك إضافة صورة أو وصف هنا مستقبلاً
    
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