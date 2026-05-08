"""
Shared Django settings for the literature project.

`dev.py` and `prod.py` import from here and add the per-environment
DEBUG / DATABASES / ALLOWED_HOSTS / proxy-header bits. Pick which one
to use via DJANGO_SETTINGS_MODULE (defaults to literature.settings.dev).

See https://docs.djangoproject.com/en/stable/topics/settings/ for an overview
and https://docs.djangoproject.com/en/stable/ref/settings/ for the full list.
"""

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read configuration from process environment first, then fall back to a `.env`
# file if present. This lets containers / CI inject config directly without
# needing to write a `.env`, while keeping the file-based workflow for local dev.
_dotenv_path = BASE_DIR / ".env"
_dotenv = dotenv_values(dotenv_path=_dotenv_path) if _dotenv_path.exists() else {}


def env(key: str, default: str | None = None) -> str | None:
    """Read a config value from os.environ, falling back to .env, then default."""
    value = os.environ.get(key)
    if value is not None:
        return value
    value = _dotenv.get(key)
    if value is not None:
        return value
    return default


def env_list(key: str, default: str) -> list[str]:
    """Read a comma-separated env value as a list of stripped, non-empty entries."""
    raw = env(key, default) or ""
    return [item.strip() for item in raw.split(",") if item.strip()]


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")
assert SECRET_KEY, "SECRET_KEY must be set via environment variable or .env file"


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # First-party
    "items.apps.ItemsConfig",
    "tagging",
    "pagehit",
    "pages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "literature.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "literature.urls"

# `OPTIONS.debug` is set per-environment in dev.py / prod.py, after this
# import, so the template debug toolbar tracks the real DEBUG flag.
TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": False,
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "literature.context_processors.global_template_variables",
            ],
        },
    },
]


WSGI_APPLICATION = "literature.wsgi.application"


# Password validation
# https://docs.djangoproject.com/en/stable/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/stable/topics/i18n/

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/stable/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"
STATICFILES_DIRS = [BASE_DIR / "literature" / "static"]

# Media files (admin-uploaded PDFs).
# In production Caddy serves /media/ directly from the bind-mounted host
# directory; locally `runserver` only serves it when literature/urls.py wires
# up `static()` under DEBUG.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# Default primary key field type
# https://docs.djangoproject.com/en/stable/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Upload limits. PDF uploads through the admin can be a few MB but rarely more
# than ~25 MB; capping at 50 MB keeps runaway multiparts from OOM-ing a worker.
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50 MiB
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50 MiB
FILE_UPLOAD_PERMISSIONS = 0o644


# Project-specific defaults consumed by literature.context_processors and
# utils.paginated_queryset. Override per-environment in dev.py / prod.py if
# needed.
DEFAULTS = {
    "entries_per_page": 25,
    "version": "0.1.0",
    # Empty by default; CLAUDE.md notes that no third-party tracker is
    # planned (the legacy todo.txt asked for Google Analytics; that decision
    # was reversed during the revival).
    "analytics_snippet": "",
}


# Logging
# https://docs.djangoproject.com/en/stable/topics/logging/
#
# Console-only by design: in dev the lines stream to the `runserver` terminal,
# and in prod gunicorn-under-Docker captures stdout/stderr so `docker logs`
# (and any host log shipper) sees them. Override the level via
# `LITERATURE_LOG_LEVEL` for occasional debug runs.
_LITERATURE_LOG_LEVEL = env("LITERATURE_LOG_LEVEL", "INFO") or "INFO"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
    },
    "loggers": {
        "literature": {
            "handlers": ["console"],
            "level": _LITERATURE_LOG_LEVEL,
            "propagate": False,
        },
        "items": {
            "handlers": ["console"],
            "level": _LITERATURE_LOG_LEVEL,
            "propagate": False,
        },
        "pages": {
            "handlers": ["console"],
            "level": _LITERATURE_LOG_LEVEL,
            "propagate": False,
        },
        "pagehit": {
            "handlers": ["console"],
            "level": _LITERATURE_LOG_LEVEL,
            "propagate": False,
        },
    },
}
