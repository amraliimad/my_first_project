from django.db import models


# جدول الملاعب
class Pitch(models.Model):
    name = models.CharField(max_length=100)  # اسم الملعب
    price_per_hour = models.DecimalField(max_digits=6, decimal_places=2)  # السعر

    def __str__(self):
        return self.name


# جدول الحجوزات
class Booking(models.Model):
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE)  # ربط الحجز بملعب معين
    player_name = models.CharField(max_length=100)
    booking_date = models.DateField()
    booking_time = models.TimeField()
from django.db import models
from django.contrib.auth.models import User

class Pitch(models.Model):
    name = models.CharField(max_length=100)
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

class Booking(models.Model):
    STATUS_CHOICES = [('Pending', 'قيد الانتظار'), ('Confirmed', 'تم التأكيد')]
    pitch = models.ForeignKey(Pitch, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.CharField(max_length=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

# تأكد أن هذا الكلاس موجود ومكتوب بهذا الشكل تماماً
class Payment(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=100)
    is_verified = models.BooleanField(default=False)