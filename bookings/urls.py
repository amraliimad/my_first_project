from django.urls import path
from . import views

urlpatterns = [
    # ── الصفحات العامة ──
    path('', views.home, name='home'),
    path('pitch/<int:pitch_id>/', views.pitch_detail, name='pitch_detail'),
    path('confirm/<int:pitch_id>/<int:hour>/', views.booking_confirm, name='booking_confirm'),
    path('success/', views.booking_success, name='booking_success'),
    path('profile/', views.user_profile, name='user_profile'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('about-us/', views.about_us, name='about_us'),

    # ── Paymob ──
    path('paymob/pay/<int:booking_id>/', views.paymob_wallet_pay, name='paymob_wallet_pay'),
    path('payment-pending/<str:booking_code>/', views.payment_pending, name='payment_pending'),
    # ── Paymob Callbacks ──
    path('paymob/callback/', views.paymob_callback, name='paymob_callback'),
    path('paymob/response/', views.paymob_response, name='paymob_response'),
    path('api/payment-status/<str:booking_code>/', views.check_payment_status, name='check_payment_status'),

    # ── 🆕 داشبورد صاحب الملعب ──
    path('owner/', views.owner_dashboard, name='owner_dashboard'),
    path('owner/pitch/<int:pitch_id>/schedule/', views.owner_schedule, name='owner_schedule'),
    path('owner/pitch/<int:pitch_id>/block/', views.owner_block_hour, name='owner_block_hour'),
    path('owner/unblock/<int:booking_id>/', views.owner_unblock_hour, name='owner_unblock_hour'),
    path('owner/booking/<int:booking_id>/update-status/', views.owner_update_booking_status, name='owner_update_booking_status'),

    # ─── 🆕 داشبورد الأرباح المالية (الجديدة) ───
    path('owner/earnings/', views.owner_earnings, name='owner_earnings'),
    path('owner/earnings/settle/', views.settle_account, name='settle_account'),
    path('owner/earnings/export-csv/', views.owner_earnings_export_csv, name='owner_earnings_export_csv'),
]
