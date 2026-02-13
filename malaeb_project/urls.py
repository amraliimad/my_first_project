from django.contrib import admin
from django.urls import path, include
from bookings import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('bookings.urls')),
    # تأكد إن السطر ده موجود ومكتوب صح 👇
    path('accounts/', include('django.contrib.auth.urls')), 
    path('signup/', views.signup, name='signup'),
]