from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# ── Sentry (early init — must be before any import that might fail) ──
from apps.accounts.sentry import init_sentry
init_sentry()

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if it exists (repo root, one level above backend/) — does not
# override environment variables already set (e.g. by Docker).
_env_file = BASE_DIR.parent / '.env'
if _env_file.is_file():
    load_dotenv(_env_file)

# ═══════════════════════════════════════════════════════════════
# 🔐 CRITICAL SECURITY — Must be set via .env in production
# ═══════════════════════════════════════════════════════════════
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or os.getenv('SECRET_KEY', 'dev-only-change-in-production')
DEBUG = (os.getenv('DJANGO_DEBUG') or os.getenv('DEBUG', 'True')).lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = [
    h.strip()
    for h in (os.getenv('DJANGO_ALLOWED_HOSTS') or os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1')).split(',')
    if h.strip()
]

# ═══════════════════════════════════════════════════════════════
# 🧩 INSTALLED APPS
# ═══════════════════════════════════════════════════════════════
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'apps.accounts',
    'apps.recuperateurs',
    'apps.nomenclature',
    'apps.traceability',
    'apps.bsd',
    'apps.bl',
    'apps.declarations',
    'apps.inspections',
    'apps.operateurs',
    'apps.administration',
    'apps.archive',
    'apps.ai_assistant',
    'apps.bc',
]

# ═══════════════════════════════════════════════════════════════
# 🔗 MIDDLEWARE
# ═══════════════════════════════════════════════════════════════
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.accounts.middleware.AuditLogMiddleware',
    'apps.accounts.middleware.SecurityHeadersMiddleware',
    'apps.accounts.middleware.SentryUserContextMiddleware',
    'apps.ai_assistant.infrastructure.middleware.RequestTrackingMiddleware',
    'apps.ai_assistant.infrastructure.middleware.RateLimitMiddleware',
    'apps.ai_assistant.infrastructure.middleware.AuditMiddleware',
]

# ---------------------------------------------------------------------------
# URLs / Auth
# ---------------------------------------------------------------------------
ROOT_URLCONF = 'config.urls'
AUTH_USER_MODEL = 'accounts.User'

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

# ═══════════════════════════════════════════════════════════════
# 🗄️  DATABASE — PostgreSQL when DB_HOST is set, SQLite otherwise
# ═══════════════════════════════════════════════════════════════
_db_host = os.getenv('DB_HOST', '')
if _db_host:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'recupdz_db'),
            'USER': os.getenv('DB_USER', 'recupdz_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'recupdz_password'),
            'HOST': _db_host,
            'PORT': os.getenv('DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '600')),
            'OPTIONS': ({'sslmode': 'require'} if os.getenv('DB_SSL_CA') else {}),
        },
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        },
    }

# ═══════════════════════════════════════════════════════════════
# 🔒 SECURITY HEADERS
# ═══════════════════════════════════════════════════════════════
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

if not DEBUG:
    SECURE_SSL_REDIRECT = (os.getenv('DJANGO_SECURE_SSL_REDIRECT') or os.getenv('SECURE_SSL_REDIRECT', 'True')).lower() in ('true', '1')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ═══════════════════════════════════════════════════════════════
# 🌐 CORS — Strict in production
# ═══════════════════════════════════════════════════════════════
_cors_origins_raw = os.getenv('DJANGO_CORS_ALLOWED_ORIGINS') or os.getenv('CORS_ALLOWED_ORIGINS', '')
if _cors_origins_raw and not DEBUG:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_raw.split(',') if o.strip()]
    CORS_ALLOW_CREDENTIALS = True
else:
    CORS_ALLOW_ALL_ORIGINS = DEBUG  # True only in dev

# ═══════════════════════════════════════════════════════════════
# 🔑 JWT AUTHENTICATION — Short-lived tokens with rotation
# ═══════════════════════════════════════════════════════════════
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'UPDATE_LAST_LOGIN': True,
}

# ═══════════════════════════════════════════════════════════════
# 🐌 RATE LIMITING (Throttling) — see DEFAULT_THROTTLE_* below
# ═══════════════════════════════════════════════════════════════
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'apps.accounts.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'apps.accounts.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/hour',
        'user': '1000/hour',
    },
    'NUM_PROXIES': int(os.getenv('DJANGO_NUM_PROXIES', '1')),
}

# ═══════════════════════════════════════════════════════════════
# 🔐 PASSWORD VALIDATORS
# ═══════════════════════════════════════════════════════════════
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ═══════════════════════════════════════════════════════════════
# 📝 LOGGING — Rotating file + console, never expose secrets
# ═══════════════════════════════════════════════════════════════
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 10_485_760,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

# ═══════════════════════════════════════════════════════════════
# 📁 STATIC & MEDIA FILES
# ═══════════════════════════════════════════════════════════════
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# i18n / Timezone
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'fr-DZ'
TIME_ZONE = 'Africa/Algiers'
USE_I18N = True
USE_TZ = True
