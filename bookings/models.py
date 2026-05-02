from django.db import models
from django.contrib.auth.models import User
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver


# ════════════════════════════════════════════════
# الخيارات المشتركة
# ════════════════════════════════════════════════

LOCATION_CHOICES = [
    ('Abbaseya',     'العباسية'),
    ('Nasr City',    'مدينة نصر'),
    ('New Cairo',    'التجمع الخامس'),
    ('Maadi',        'المعادي'),
    ('Shoubra',      'شبرا'),
    ('Dokki',        'الدقي'),
    ('Giza',         'الجيزة'),
    ('Zamalek',      'الزمالك'),
    ('Haram',        'الهرم'),
    ('Faisal',       'فيصل'),
    ('Obour',        'العبور'),
    ('Shorouk',      'الشروق'),
    ('October',      '6 أكتوبر'),
    ('Sheikh Zayed', 'الشيخ زايد'),
    ('Helwan',       'حلوان'),
    ('Mokattam',     'المقطم'),
    ('Alexandria',   'الإسكندرية'),
]

SPECIALTY_CHOICES = [
    ('general',       'طب عام'),
    ('internal',      'باطنة'),
    ('cardiology',    'قلب وأوعية دموية'),
    ('orthopedics',   'عظام'),
    ('pediatrics',    'أطفال'),
    ('dermatology',   'جلدية وتجميل'),
    ('gynecology',    'نساء وتوليد'),
    ('ophthalmology', 'عيون'),
    ('ent',           'أنف وأذن وحنجرة'),
    ('neurology',     'مخ وأعصاب'),
    ('psychiatry',    'نفسية'),
    ('dentistry',     'أسنان'),
    ('urology',       'مسالك بولية'),
    ('oncology',      'أورام'),
    ('endocrinology', 'غدد صماء وسكر'),
    ('other',         'أخرى'),
]


# ════════════════════════════════════════════════
# 1. جدول العيادات (Clinics)
# ════════════════════════════════════════════════
class Clinic(models.Model):
    """
    العيادة هي الكيان الرئيسي.
    ليها مالك واحد (User) وبتحتوي على دكتور أو أكتر.
    """

    owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='owned_clinics',
        verbose_name="مالك العيادة"
    )

    # البيانات الأساسية
    name               = models.CharField(max_length=150, verbose_name="اسم العيادة / المجمع الطبي")
    description        = models.TextField(blank=True, verbose_name="نبذة عن العيادة")
    image              = models.ImageField(upload_to='clinic_images/', blank=True, null=True, verbose_name="صورة العيادة")
    is_multi_specialty = models.BooleanField(
        default=False,
        verbose_name="مجمع طبي متعدد التخصصات؟",
        help_text="لو True → المريض يختار التخصص أولاً ثم الدكتور"
    )

    # الموقع
    location        = models.CharField(max_length=50, choices=LOCATION_CHOICES, default='Nasr City', verbose_name="المنطقة")
    address         = models.CharField(max_length=255, blank=True, verbose_name="العنوان بالتفصيل")
    google_map_link = models.URLField(blank=True, null=True, verbose_name="رابط جوجل ماب")
    latitude        = models.FloatField(blank=True, null=True)
    longitude       = models.FloatField(blank=True, null=True)

    # التواصل
    phone_number    = models.CharField(max_length=15, blank=True, verbose_name="رقم العيادة")
    whatsapp_number = models.CharField(max_length=15, blank=True, verbose_name="واتساب")

    # العمولة على مستوى العيادة
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=5.00,
        verbose_name="نسبة عمولة الموقع (%)"
    )

    is_available = models.BooleanField(default=True, verbose_name="تقبل حجوزات جديدة؟")
    is_new       = models.BooleanField(default=True,  verbose_name="عيادة جديدة؟")
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "عيادة"
        verbose_name_plural = "العيادات"

    def __str__(self):
        return f"{self.name} — {self.get_location_display()}"

    def get_specialties_display(self):
        """قائمة التخصصات الموجودة في العيادة للعرض"""
        specs = self.doctors.filter(is_active=True).values_list('specialty', flat=True).distinct()
        spec_map = dict(SPECIALTY_CHOICES)
        return [spec_map.get(s, s) for s in specs]


# ════════════════════════════════════════════════
# 2. جدول الدكاترة (Doctors)
# ════════════════════════════════════════════════
class Doctor(models.Model):
    """
    كل دكتور مرتبط بعيادة.
    عنده ساعات عمل وأيام خاصة بيه — مختلفة عن باقي دكاترة نفس العيادة.
    """

    TITLE_CHOICES = [
        ('dr',         'د.'),
        ('prof',       'أ.د.'),
        ('consultant', 'استشاري'),
    ]

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name='doctors',
        verbose_name="العيادة"
    )

    # البيانات الأساسية
    name          = models.CharField(max_length=100, verbose_name="اسم الدكتور")
    title         = models.CharField(max_length=20, choices=TITLE_CHOICES, default='dr', verbose_name="اللقب")
    specialty     = models.CharField(max_length=30, choices=SPECIALTY_CHOICES, default='general', verbose_name="التخصص")
    bio           = models.TextField(blank=True, verbose_name="نبذة عن الدكتور")
    image         = models.ImageField(upload_to='doctor_images/', blank=True, null=True, verbose_name="صورة الدكتور")

    # السعر ومدة الكشف
    price         = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="سعر الكشف (ج.م)")
    slot_duration = models.IntegerField(default=30, verbose_name="مدة الكشف (بالدقائق)")

    # ساعات العمل الخاصة بالدكتور
    opening_hour  = models.IntegerField(default=9,  verbose_name="بداية الدوام (ساعة)")
    closing_hour  = models.IntegerField(default=17, verbose_name="نهاية الدوام (ساعة)")

    # أيام العمل الخاصة بالدكتور
    works_sat = models.BooleanField(default=True,  verbose_name="السبت")
    works_sun = models.BooleanField(default=True,  verbose_name="الأحد")
    works_mon = models.BooleanField(default=True,  verbose_name="الاثنين")
    works_tue = models.BooleanField(default=True,  verbose_name="الثلاثاء")
    works_wed = models.BooleanField(default=True,  verbose_name="الأربعاء")
    works_thu = models.BooleanField(default=True,  verbose_name="الخميس")
    works_fri = models.BooleanField(default=False, verbose_name="الجمعة")

    is_active     = models.BooleanField(default=True, verbose_name="متاح للحجز؟")
    display_order = models.IntegerField(default=0, verbose_name="ترتيب العرض")

    class Meta:
        verbose_name        = "دكتور"
        verbose_name_plural = "الدكاترة"
        ordering            = ['display_order', 'name']

    def __str__(self):
        return f"{self.get_title_display()} {self.name} — {self.get_specialty_display()} ({self.clinic.name})"

    @property
    def full_name(self):
        return f"{self.get_title_display()} {self.name}"

    def works_on_day(self, weekday_int):
        """
        weekday_int من Python datetime:
        0=Mon 1=Tue 2=Wed 3=Thu 4=Fri 5=Sat 6=Sun
        """
        mapping = {
            5: self.works_sat,
            6: self.works_sun,
            0: self.works_mon,
            1: self.works_tue,
            2: self.works_wed,
            3: self.works_thu,
            4: self.works_fri,
        }
        return mapping.get(weekday_int, False)


# ════════════════════════════════════════════════
# 3. جدول المواعيد (Appointments)
# ════════════════════════════════════════════════
class Appointment(models.Model):

    STATUS_CHOICES = [
        ('Pending',   'قيد المراجعة — في انتظار تأكيد الدفع'),
        ('Confirmed', 'مؤكد'),
        ('Attended',  'حضر وانتهى الكشف'),
        ('No-Show',   'لم يحضر المريض'),
        ('Cancelled', 'ملغي'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('Full',        'دفع كامل'),
        ('Deposit',     'دفع عربون'),
        ('PayAtClinic', 'دفع في العيادة'),
    ]

    # الحجز دايماً بـ Doctor — مش بـ Clinic
    doctor  = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='appointments',
        verbose_name="الدكتور"
    )
    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='appointments',
        verbose_name="المريض"
    )

    date         = models.DateField(verbose_name="تاريخ الموعد", db_index=True)
    time         = models.CharField(max_length=10, verbose_name="وقت الموعد (HH:MM)")
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', verbose_name="الحالة", db_index=True)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='Full', verbose_name="نوع الدفع")
    booking_code = models.CharField(max_length=10, unique=True, editable=False, null=True, verbose_name="كود الحجز")
    complaint    = models.TextField(blank=True, verbose_name="الشكوى / سبب الزيارة")

    # حجز يدوي من السكرتيرة
    is_manual     = models.BooleanField(default=False, verbose_name="حجز يدوي؟")
    patient_name  = models.CharField(max_length=100, blank=True, verbose_name="اسم المريض (يدوي)")
    patient_phone = models.CharField(max_length=15,  blank=True, verbose_name="رقم المريض (يدوي)")

    # التسوية المالية
    is_settled = models.BooleanField(default=False, verbose_name="تمت التسوية؟")
    settled_at = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ التسوية")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "موعد"
        verbose_name_plural = "المواعيد"
        ordering            = ['-date', '-time']
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'date', 'time'],
                condition=~models.Q(status__in=['Cancelled', 'No-Show']),
                name='unique_active_appointment'
            )
        ]

    def save(self, *args, **kwargs):
        if not self.booking_code:
            self.booking_code = str(uuid.uuid4()).upper()[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        name = self.patient_name if self.is_manual else (self.patient.username if self.patient else '—')
        return f"{name} — {self.doctor.full_name} ({self.date} {self.time})"

    @property
    def clinic(self):
        """shortcut: appointment.clinic"""
        return self.doctor.clinic


# ════════════════════════════════════════════════
# 4. جدول المدفوعات
# ════════════════════════════════════════════════
class AppointmentPayment(models.Model):

    PAYMENT_METHODS = [
        ('Vodafone', 'فودافون كاش'),
        ('Instapay', 'إنستا باي'),
        ('Cash',     'دفع في العيادة'),
        ('Fawry',    'فوري'),
    ]

    appointment     = models.OneToOneField(
        Appointment, on_delete=models.CASCADE,
        related_name='payment_details',
        verbose_name="الموعد"
    )
    transaction_id  = models.CharField(max_length=100, blank=True, null=True)
    payment_method  = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='Cash', verbose_name="طريقة الدفع")
    is_verified     = models.BooleanField(default=False, verbose_name="تم التحقق؟")
    paymob_order_id = models.CharField(max_length=100, blank=True, null=True)
    amount_cents    = models.IntegerField(default=0, verbose_name="المبلغ بالقروش")
    timestamp       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "عملية دفع"
        verbose_name_plural = "المدفوعات"

    def __str__(self):
        return f"دفع {self.appointment.booking_code} — {self.get_payment_method_display()}"


# ════════════════════════════════════════════════
# 5. جدول التقييمات
# ════════════════════════════════════════════════
class DoctorReview(models.Model):

    doctor     = models.ForeignKey(Doctor, related_name='reviews', on_delete=models.CASCADE, verbose_name="الدكتور")
    patient    = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="المريض")
    rating     = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="التقييم")
    comment    = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "تقييم"
        verbose_name_plural = "التقييمات"
        ordering            = ['-created_at']
        unique_together     = [['doctor', 'patient']]

    def __str__(self):
        return f"{self.patient.username} — {self.doctor.full_name} ({self.rating}★)"


# ════════════════════════════════════════════════
# 6. الملف الشخصي
# ════════════════════════════════════════════════
class UserProfile(models.Model):
    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    middle_name   = models.CharField(max_length=50, blank=True, null=True)
    phone_number  = models.CharField(max_length=15, blank=True, null=True, verbose_name="رقم الموبايل")
    date_of_birth = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name        = "ملف شخصي"
        verbose_name_plural = "الملفات الشخصية"

    def __str__(self):
        return f"بروفايل {self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()