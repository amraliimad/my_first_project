from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.conf.urls.i18n import i18n_patterns
from bookings import views as booking_views

# 1. روابط بدون i18n (تغيير اللغة فقط)
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
]

# 2. باقي الروابط مع دعم اللغات
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('signup/', booking_views.signup, name='signup'),
    path('', include('bookings.urls')),
    prefix_default_language=True,
)

# 3. ملفات الميديا والستاتيك
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# 4. تخصيص لوحة التحكم
admin.site.site_header = "إدارة موقع ملاعبك"
admin.site.site_title  = "لوحة تحكم ملاعبك"
admin.site.index_title = "مرحباً بك في مدير نظام الحجوزات"