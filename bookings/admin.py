from django.contrib import admin
from .models import Pitch, Booking, Payment, PitchPricing, Review, UserProfile


class PitchPricingInline(admin.TabularInline):
    model = PitchPricing
    extra = 1
    verbose_name = "سعر خاص / فترة زمنية"
    verbose_name_plural = "قائمة الأسعار المتغيرة"


class PitchAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'location', 'price_per_hour','commission_percentage','size', 'phone_number', 'opening_hour', 'closing_hour')
    list_filter = ('location', 'floor_type', 'size', 'owner')
    search_fields = ('name', 'location', 'owner__username')
    list_editable = ('opening_hour', 'closing_hour','commission_percentage')
    inlines = [PitchPricingInline]


class BookingAdmin(admin.ModelAdmin):
    # ✅ إضافة is_settled للرؤية والتعديل المباشر
    list_display = ('booking_code', 'pitch', 'user', 'date', 'time', 'status', 'payment_type', 'is_manual', 'is_settled')
    list_filter = ('status', 'is_settled', 'date', 'pitch', 'is_manual', 'payment_type')
    search_fields = ('booking_code', 'user__username', 'customer_name')
    list_editable = ('status', 'is_settled')
    date_hierarchy = 'date' # ✅ إضافة فلتر التاريخ الزمني السريع

# ─────────────────────────────────────────────────────────
# 🆕 إضافة لوحة تحكم المدفوعات (FinTech Admin)
# ─────────────────────────────────────────────────────────
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('get_booking_code', 'payment_method', 'get_amount', 'is_verified', 'transaction_id', 'timestamp')
    list_filter = ('is_verified', 'payment_method', 'timestamp')
    search_fields = ('transaction_id', 'paymob_order_id', 'booking__booking_code')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'

    # دالة لجلب كود الحجز المرتبط بسهولة
    def get_booking_code(self, obj):
        return obj.booking.booking_code
    get_booking_code.short_description = 'كود الحجز'

    # دالة لعرض المبلغ بالجنيه بدلاً من القروش
    def get_amount(self, obj):
        return f"{obj.amount_cents / 100} ج.م"
    get_amount.short_description = 'المبلغ'

# ─────────────────────────────────────────────────────────
# 🆕 إضافة لوحة تحكم التقييمات
# ─────────────────────────────────────────────────────────
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('pitch', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'pitch', 'created_at')
    search_fields = ('pitch__name', 'user__username', 'comment')
    readonly_fields = ('created_at',)

admin.site.register(Pitch, PitchAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Payment, PaymentAdmin) # ✅ تم التحديث
admin.site.register(Review, ReviewAdmin)   # ✅ تم التحديث

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number')
    search_fields = ('user__username', 'phone_number')

admin.site.register(UserProfile, UserProfileAdmin)
