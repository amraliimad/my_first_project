from django.contrib import admin
from .models import Clinic, Doctor, Appointment, AppointmentPayment, DoctorReview, UserProfile


class DoctorInline(admin.TabularInline):
    model = Doctor
    extra = 1

class ClinicAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'location', 'phone_number', 'is_available', 'commission_percentage')
    list_filter = ('location', 'is_available', 'is_multi_specialty')
    search_fields = ('name', 'location', 'owner__username')
    inlines = [DoctorInline]

class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'specialty', 'clinic', 'price', 'is_active')
    list_filter = ('specialty', 'is_active', 'clinic')
    search_fields = ('name', 'clinic__name')

class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('booking_code', 'doctor', 'patient', 'date', 'time', 'status', 'payment_type', 'is_settled')
    list_filter = ('status', 'is_settled', 'date', 'doctor__clinic')
    search_fields = ('booking_code', 'patient__username', 'patient_name', 'patient_phone')
    list_editable = ('status',)
    readonly_fields = ('booking_code', 'created_at', 'settled_at')

class AppointmentPaymentAdmin(admin.ModelAdmin):
    list_display = ('appointment', 'payment_method', 'is_verified', 'transaction_id', 'timestamp')
    list_filter = ('is_verified', 'payment_method')

class DoctorReviewAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'patient', 'rating', 'created_at')
    list_filter = ('rating', 'doctor')

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number')
    search_fields = ('user__username', 'phone_number')

admin.site.register(Clinic, ClinicAdmin)
admin.site.register(Doctor, DoctorAdmin)
admin.site.register(Appointment, AppointmentAdmin)
admin.site.register(AppointmentPayment, AppointmentPaymentAdmin)
admin.site.register(DoctorReview, DoctorReviewAdmin)
admin.site.register(UserProfile, UserProfileAdmin)