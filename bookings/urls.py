from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('pitch/<int:pitch_id>/', views.pitch_detail, name='pitch_detail'),
    path('confirm/<int:pitch_id>/<int:hour>/', views.booking_confirm, name='booking_confirm'),
    path('success/', views.booking_success, name='booking_success'),
    path('profile/', views.user_profile, name='user_profile'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('about-us/', views.about_us, name='about_us'),

    # Paymob URLs
    path('paymob/pay/<int:booking_id>/', views.paymob_wallet_pay, name='paymob_wallet_pay'),
    path('payment-pending/<str:booking_code>/', views.payment_pending, name='payment_pending'),
]