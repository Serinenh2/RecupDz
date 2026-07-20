from pathlib import Path
from datetime import timedelta
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if it exists (does not override existing env vars)
_env_file = BASE_DIR.parent / '.env'
if _env_file.is_file():
    load_dotenv(_env_file)

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'recup-dz-dev-secret-key-not-for-production',
)

DEBUG = os.environ.get('DEBUG', 'true').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]

# ---------------------------------------------------------------------------
# Installed apps
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
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

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
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
    'apps.ai_assistant.infrastructure.middleware.SecurityHeadersMiddleware',
    'apps.ai_assistant.infrastructure.middleware.RateLimitMiddleware',
    'apps.ai_assistant.infrastructure.middleware.AuditMiddleware',
    'apps.ai_assistant.infrastructure.middleware.RequestTrackingMiddleware',
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

# ---------------------------------------------------------------------------
# Database — PostgreSQL when DB_HOST is set, SQLite otherwise
# ---------------------------------------------------------------------------
_db_host = os.environ.get('DB_HOST', '')
if _db_host:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'recupdz_db'),
            'USER': os.environ.get('DB_USER', 'recupdz_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'recupdz_password'),
            'HOST': _db_host,
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {},
        },
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        },
    }

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
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
}

# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# ---------------------------------------------------------------------------
# CORS — restrict to listed origins in production
# ---------------------------------------------------------------------------
_cors_origins_raw = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if _cors_origins_raw:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [
        o.strip()
        for o in _cors_origins_raw.split(',')
        if o.strip()
    ]
else:
    # Dev: allow all.  Production: MUST set CORS_ALLOWED_ORIGINS.
    CORS_ALLOW_ALL_ORIGINS = DEBUG

# ---------------------------------------------------------------------------
# Static / Media
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
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

# ---------------------------------------------------------------------------
# Security (applied when DEBUG=False)
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'false').lower() in ('true', '1', 'yes')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Logging — structured JSON in production, human-readable in dev
# ---------------------------------------------------------------------------
_log_level = os.environ.get('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO')
_log_format = os.environ.get('LOG_FORMAT', 'text')

if _log_format == 'json':
    _log_formatter = {
        '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
        'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
        'datefmt': '%Y-%m-%dT%H:%M:%S',
    }
    _log_datefmt = '%Y-%m-%dT%H:%M:%S'
else:
    _log_formatter = {
        '()': 'logging.Formatter',
        'format': '[{asctime}] {levelname} {name} {message}',
        'datefmt': '%Y-%m-%d %H:%M:%S',
        'style': '{',
    }
    _log_datefmt = None

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': _log_formatter,
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': _log_level,
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': _log_level,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'apps.ai_assistant': {
            'handlers': ['console'],
            'level': _log_level,
            'propagate': False,
        },
        'apps.ai_assistant.enterprise': {
            'handlers': ['console'],
            'level': _log_level,
            'propagate': False,
        },
    },
}
