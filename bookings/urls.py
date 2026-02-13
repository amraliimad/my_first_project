from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('pitch/<int:pitch_id>/', views.pitch_detail, name='pitch_detail'),
    # تأكد من وجود <int:hour> هنا لأن الدالة في الـ views بتطلبه
    path('confirm/<int:pitch_id>/<int:hour>/', views.booking_confirm, name='booking_confirm'),
    path('success/', views.booking_success, name='booking_success'),
]