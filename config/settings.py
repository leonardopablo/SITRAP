from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")
DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY")
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("dev-")):
    raise ImproperlyConfigured("Configure a strong SECRET_KEY outside development.")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.accounts",
    "apps.sync",
    "apps.audit",
    "apps.catalog",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": env.db("DATABASE_URL")}
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("SITRAP requires PostgreSQL, including tests.")
DATABASES["default"]["CONN_MAX_AGE"] = 60
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=43200)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = False
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
X_FRAME_OPTIONS = "DENY"
OFFLINE_PREPARATION_DAYS = env.int("OFFLINE_PREPARATION_DAYS", default=7)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.SessionAuth"],
    "DEFAULT_PERMISSION_CLASSES": ["apps.accounts.authentication.ReadyAccount"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.BoundedPagination",
    "PAGE_SIZE": 50,
    "COERCE_DECIMAL_TO_STRING": True,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
SPECTACULAR_SETTINGS = {
    "TITLE": "SITRAP API",
    "VERSION": "0.1.0",
    "DESCRIPTION": "MVP de trazabilidad de leche. Contrato incremental; solo rutas implementadas.",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

AUTH_USER_MODEL = "accounts.User"

CSRF_FAILURE_VIEW = "apps.common.errors.csrf_failure"
REST_FRAMEWORK["EXCEPTION_HANDLER"] = "apps.common.errors.error_handler"
LOGIN_WINDOW_SECONDS = env.int("LOGIN_WINDOW_SECONDS", default=300)
LOGIN_USER_LIMIT = env.int("LOGIN_USER_LIMIT", default=5)
LOGIN_IP_LIMIT = env.int("LOGIN_IP_LIMIT", default=100)

SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["apps.accounts.authentication.ReadyAccount"]

SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"] = {"UnitCodeEnum": ["L", "KG", "UN"]}
