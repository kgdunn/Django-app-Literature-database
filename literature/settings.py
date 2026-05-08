"""
Django settings for the literature project.

This is the Phase-1 monolithic settings file: dev-friendly defaults,
SQLite, DEBUG=True, hardcoded SECRET_KEY. Phase 2 will split this into
literature/settings/{base,dev,prod,ci}.py with env-driven configuration.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# SECURITY WARNING: keep the secret key used in production secret!
# Phase 2 will move this into literature/settings/base.py and read it from
# the SECRET_KEY environment variable.
SECRET_KEY = "d_f&!d@2!@=^=o2j)+w^&d#qigs3qtw3&cbbc2exk3#9g_*w7%"  # noqa: S105

DEBUG = True
ALLOWED_HOSTS: list[str] = []


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # First-party apps
    "items.apps.ItemsConfig",
    "tagging",
    "pagehit",
    "pages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "literature.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
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


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static + media. Phase 7 (Docker) bind-mounts data/media and data/static at
# /app/{media,static}; until then we serve them out of BASE_DIR.
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")
STATICFILES_DIRS = [os.path.join(BASE_DIR, "literature", "static")]

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Project-specific defaults consumed by literature.context_processors and
# utils.paginated_queryset. Override on a per-deploy basis once Phase 2 lands
# the env-driven settings split.
DEFAULTS = {
    "entries_per_page": 25,
    "version": "0.1.0",
    # Empty by default; CLAUDE.md notes that no third-party tracker is
    # planned (the legacy todo.txt asked for Google Analytics; that decision
    # was reversed during the revival).
    "analytics_snippet": "",
}


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "literature": {
            "handlers": ["console"],
            "level": os.environ.get("LITERATURE_LOG_LEVEL", "INFO"),
        },
        "items": {
            "handlers": ["console"],
            "level": os.environ.get("LITERATURE_LOG_LEVEL", "INFO"),
        },
        "pages": {
            "handlers": ["console"],
            "level": os.environ.get("LITERATURE_LOG_LEVEL", "INFO"),
        },
    },
}
