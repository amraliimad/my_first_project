import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv
from django.utils.translation import gettext_lazy as _


# 1. تحميل الإعدادات من ملف .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# 2. جلب الأسرار من البيئة
SECRET_KEY = 'django-insecure-change-me-later-to-something-very-long-12345'
DEBUG = True

# 3. الروابط المسموح بها
# أضف رابط موقعك على PythonAnywhere هنا بجانب الـ localhost
ALLOWED_HOSTS = ['mal3abonline.me', 'www.mal3abonline.me', '.herokuapp.com']

# --- Application definition ---

INSTALLED_APPS = [
    "bookings",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    "django.contrib.sessions.middleware.SessionMiddleware",
    'django.middleware.locale.LocaleMiddleware', # ترجمه
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "malaeb_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates"
        ],  # التعديل هنا: شلنا bookings وخليناها templates بس
        "APP_DIRS": True,  # ده هيخلي جانغو يدور جوه bookings أوتوماتيك متقلقش
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


WSGI_APPLICATION = "malaeb_project.wsgi.application"

# --- Database ---

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# --- Internationalization ---

# 1. تعريف اللغات
LANGUAGE_CODE = 'ar' # اللغة الافتراضية
LANGUAGES = [
    ('ar', _('Arabic')),
    ('en', _('English')),
]
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# --- Static files ---

STATIC_URL = "static/"

# ضيف الجزء ده ضروري جداً
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Authentication Redirects ---

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "home"

# --- SECURITY SETTINGS ---
# الإعدادات دي هتشتغل بس لما DEBUG تكون False (يعني على السيرفر الحقيقي)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
else:
    # على جهازك الشخصي، نغلق هذه الإعدادات لتجنب أخطاء المتصفح
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# إعدادات رفع الملفات والصور
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
# السماح لـ Django بقبول الطلبات من رابط موقعك
CSRF_TRUSTED_ORIGINS = [
    'https://amrali011.pythonanywhere.com', # للسيرفر
    'http://127.0.0.1:8000',                 # لجهازك
    'http://localhost:8000',                 # لجهازك برضه
]

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# مكان ملفات الترجمة
LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

import dj_database_url
import os

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Heroku PostgreSQL integration
db_from_env = dj_database_url.config(conn_max_age=600, ssl_require=True)
DATABASES['default'].update(db_from_env)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES['default'] = dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=600,
        ssl_require=True,
    )