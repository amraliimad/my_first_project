"""
URL configuration for malaeb_project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from bookings import views as booking_views  # استيراد بلقب لتجنب تضارب الأسماء

urlpatterns = [
    # --- واجهة الإدارة ---
    path("admin/", admin.site.urls),
    # --- نظام المصادقة (Auth System) ---
    # تسجيل الخروج مخصص للتحويل للصفحة الرئيسية مباشرة
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),
    # تضمين مسارات Django الجاهزة (login, password_reset, etc.)
    path("accounts/", include("django.contrib.auth.urls")),
    # مسار إنشاء حساب جديد
    path("signup/", booking_views.signup, name="signup"),
    # --- تطبيق الملاعب (Bookings App) ---
    path("", include("bookings.urls")),
]

# --- دعم ملفات الميديا والصور أثناء التطوير ---
# هذا السطر ضروري جداً لتظهر صور الملاعب التي ترفعها في لوحة التحكم
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# --- تخصيص لوحة تحكم الإدارة (اختياري لكن احترافي) ---
admin.site.site_header = "إدارة موقع ملاعبك"
admin.site.site_title = "لوحة تحكم ملاعبك"
admin.site.index_title = "مرحباً بك في مدير نظام الحجوزات"
