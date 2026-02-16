from django.contrib import admin
from .models import Pitch, Booking, Payment, PitchPricing, Review

# 1. إعداد جدول الأسعار ليظهر داخل صفحة الملعب
class PitchPricingInline(admin.TabularInline):
    model = PitchPricing
    extra = 1
    verbose_name = "سعر خاص / فترة زمنية"
    verbose_name_plural = "قائمة الأسعار المتغيرة (صباحي/مسائي/عروض)"
    help_text = "مثال: من الساعة 9 إلى 16 (الساعة 4 عصراً) بسعر 100 جنية."

# 2. تخصيص لوحة تحكم الملاعب
class PitchAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'price_per_hour', 'size', 'phone_number')
    list_filter = ('location', 'floor_type', 'size')
    search_fields = ('name', 'location')
    inlines = [PitchPricingInline] # دي السطر السحري اللي بيدمج الأسعار جوه الملعب

# 3. تخصيص لوحة الحجوزات
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_code', 'pitch', 'user', 'date', 'time', 'status', 'payment_type')
    list_filter = ('status', 'date', 'pitch')
    search_fields = ('booking_code', 'user__username')
    list_editable = ('status',) # عشان تغير الحالة بسرعة من برة

# التسجيل النهائي
admin.site.register(Pitch, PitchAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Payment)
admin.site.register(Review)
# admin.site.register(PitchPricing) # شلنا دي لأنها بقت جوه Pitch خلاص
