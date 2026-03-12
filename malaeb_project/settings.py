import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv
from django.utils.translation import gettext_lazy as _


# ═══════════════════════════════════════════
# 1. الإعدادات الأساسية
# ═══════════════════════════════════════════
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-unsafe-key-do-not-use-in-production'
    else:
        raise RuntimeError("SECRET_KEY environment variable is not set!")
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = [
    'mal3abonline-50a569f7c025.herokuapp.com',
    'mal3abonline.me',
    'www.mal3abonline.me',
    'localhost',
    '127.0.0.1',
]


# ═══════════════════════════════════════════
# 2. التطبيقات
# ═══════════════════════════════════════════
INSTALLED_APPS = [
    "bookings",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "cloudinary_storage",  # 🆕
    "django.contrib.staticfiles",
    "cloudinary",

]


# ═══════════════════════════════════════════
# 3. الوسطاء (Middleware) - بدون تكرار!
# ═══════════════════════════════════════════
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",       # ← مرة واحدة بس!
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ═══════════════════════════════════════════
# 4. URLs & Templates
# ═══════════════════════════════════════════
ROOT_URLCONF = "malaeb_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                'bookings.context_processors.user_pitches',
            ],
        },
    },
]

WSGI_APPLICATION = "malaeb_project.wsgi.application"


# ═══════════════════════════════════════════
# 5. قاعدة البيانات - مرة واحدة بس!
# ═══════════════════════════════════════════
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=os.environ.get('DATABASE_URL', '').startswith('postgres'),
    )
}


# ═══════════════════════════════════════════
# 6. اللغات والتوقيت
# ═══════════════════════════════════════════
LANGUAGE_CODE = 'ar'
LANGUAGES = [
    ('ar', _('Arabic')),
    ('en', _('English')),
]
TIME_ZONE = "Africa/Cairo"      # ← مصر مش UTC!
USE_I18N = True
USE_TZ = True
# تم إزالة USE_L10N لتجنب تحذيرات Django الحديثة
LOCALE_PATHS = [BASE_DIR / 'locale']


# ═══════════════════════════════════════════
# 7. الملفات الثابتة والميديا (Static & Cloudinary)
# ═══════════════════════════════════════════
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')# استخدام WhiteNoise لضغط الملفات الثابتة (CSS/JS)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── إعدادات Cloudinary لصور الملاعب (Media) ──
MEDIA_URL = '/media/'
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}


# ═══════════════════════════════════════════
# 8. تسجيل الدخول والخروج
# ═══════════════════════════════════════════
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'home'
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ═══════════════════════════════════════════
# 9. CSRF - مرة واحدة بس!
# ═══════════════════════════════════════════
CSRF_TRUSTED_ORIGINS = [
    'https://mal3abonline.me',
    'https://www.mal3abonline.me',
    'https://mal3abonline-50a569f7c025.herokuapp.com',
    'https://accept.paymob.com',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]


# ═══════════════════════════════════════════
# 10. إعدادات الأمان (Production فقط)
# ═══════════════════════════════════════════
X_FRAME_OPTIONS = 'SAMEORIGIN'
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ═══════════════════════════════════════════
# 11. إعدادات Paymob للدفع الإلكتروني
# ═══════════════════════════════════════════
PAYMOB_API_KEY = os.environ.get('PAYMOB_API_KEY')
PAYMOB_INTEGRATION_ID_WALLET = os.environ.get('PAYMOB_INTEGRATION_ID_WALLET')
PAYMOB_HMAC_SECRET = os.environ.get('PAYMOB_HMAC_SECRET')
SUPPORT_WHATSAPP = os.environ.get('SUPPORT_WHATSAPP', '201034819083')
PAYMOB_BASE_URL = os.environ.get('PAYMOB_BASE_URL', 'https://accept.paymob.com/api')