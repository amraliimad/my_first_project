from django.urls import path
from . import views

urlpatterns = [
    # ── عام ──
    path('', views.home, name='home'),
    path('about-us/', views.about_us, name='about_us'),

    # ── العيادات ──
    path('clinic/<int:clinic_id>/', views.clinic_detail, name='clinic_detail'),

    # ── الدكاترة ──
    path('doctor/<int:doctor_id>/', views.doctor_detail, name='doctor_detail'),
    path('doctor/<int:doctor_id>/book/<str:time_str>/', views.appointment_confirm, name='appointment_confirm'),

    # ── المواعيد ──
    path('appointment/success/', views.appointment_success, name='appointment_success'),
    path('appointment/cancel/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),

    # ── الملف الشخصي ──
    path('profile/', views.user_profile, name='user_profile'),

    # ── داشبورد المالك ──
    path('owner/', views.owner_dashboard, name='owner_dashboard'),
    path('owner/doctor/<int:doctor_id>/schedule/', views.owner_schedule, name='owner_schedule'),
    path('owner/doctor/<int:doctor_id>/block/', views.owner_block_slot, name='owner_block_slot'),
    path('owner/unblock/<int:appointment_id>/', views.owner_unblock_slot, name='owner_unblock_slot'),
    path('owner/appointment/<int:appointment_id>/update-status/', views.owner_update_appointment_status, name='owner_update_appointment_status'),
    path('owner/appointment/<int:appointment_id>/confirm-payment/', views.owner_confirm_payment, name='owner_confirm_payment'),

    # ── الأرباح ──
    path('owner/earnings/', views.owner_earnings, name='owner_earnings'),
    path('owner/earnings/settle/', views.settle_account, name='settle_account'),
    path('owner/earnings/export-csv/', views.owner_earnings_export_csv, name='export_earnings_csv'),
]