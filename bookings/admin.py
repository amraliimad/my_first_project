from django.contrib import admin
from .models import Pitch, Booking, Payment, PitchPricing, Review


class PitchPricingInline(admin.TabularInline):
    model = PitchPricing
    extra = 1
    verbose_name = "سعر خاص / فترة زمنية"
    verbose_name_plural = "قائمة الأسعار المتغيرة"


class PitchAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'location', 'price_per_hour', 'size', 'phone_number', 'opening_hour', 'closing_hour')
    list_filter = ('location', 'floor_type', 'size', 'owner')
    search_fields = ('name', 'location', 'owner__username')
    list_editable = ('opening_hour', 'closing_hour')
    inlines = [PitchPricingInline]


class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_code', 'pitch', 'user', 'date', 'time', 'status', 'payment_type', 'is_manual')
    list_filter = ('status', 'date', 'pitch', 'is_manual')
    search_fields = ('booking_code', 'user__username', 'customer_name')
    list_editable = ('status',)


admin.site.register(Pitch, PitchAdmin)
admin.site.register(Booking, BookingAdmin)
admin.site.register(Payment)
admin.site.register(Review)