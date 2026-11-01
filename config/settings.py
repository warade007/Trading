from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from config.local_secrets import django_secret, LocalKeyError

BASE_DIR = Path(__file__).resolve().parent.parent
try:
    SECRET_KEY = django_secret()
except LocalKeyError as exc:
    raise ImproperlyConfigured(str(exc)) from None
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1"]
RESEARCH_MODE = True
LIVE_TRADING_ENABLED = False
RESEARCH_ARCHIVE_DIR = BASE_DIR / "data" / "raw"
RESEARCH_ARCHIVE_BUDGET = 256 * 1024 * 1024
BROKER_FERNET_KEYS = None  # None loads the separate DPAPI/environment keyring on demand.
BROKER_CALLBACK_URL = "http://127.0.0.1:8001/kite/callback"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "research", "brokers"]
MIDDLEWARE = [
    "research.middleware.LocalReadOnlyMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]},
}]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": BASE_DIR / "data" / "research.sqlite3",
    "OPTIONS": {"timeout": 20},
}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "Asia/Kolkata"
USE_TZ = True
LANGUAGE_CODE = "en-in"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
CSRF_FAILURE_VIEW = "brokers.views.csrf_failure"
SESSION_COOKIE_NAME = "trading_research_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_ENGINE = "django.contrib.sessions.backends.db"
CSRF_COOKIE_NAME = "trading_research_csrf"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
# Plain HTTP is intentionally limited to loopback, so Secure cookies cannot be used.
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/settings/broker/"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "filters": {"safe": {"()": "brokers.logging.SafeRequestFilter"}},
    "handlers": {
        "safe_console": {"class": "logging.StreamHandler", "filters": ["safe"]},
        "discard": {"class": "logging.NullHandler"},
    },
    "loggers": {
        "django": {"handlers": ["safe_console"], "level": "INFO", "propagate": False},
        "django.server": {"handlers": ["safe_console"], "level": "INFO", "propagate": False},
        "kiteconnect": {"handlers": ["discard"], "propagate": False},
        "requests": {"handlers": ["discard"], "propagate": False},
        "urllib3": {"handlers": ["discard"], "propagate": False},
    },
}
