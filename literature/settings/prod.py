"""Production settings: Postgres + DEBUG=False + Caddy/Cloudflare proxy headers."""

from .base import *  # noqa: F401,F403
from .base import env, env_list

DEBUG = False

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ".literature.learnche.org,127.0.0.1")

# Caddy terminates TLS on the host and proxies plain HTTP to gunicorn.
# This header tells Django the request was originally HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Required by Django 4.x for any non-GET request (e.g. admin login) when the
# request reaches Django over HTTPS via a reverse proxy.
CSRF_TRUSTED_ORIGINS = [
    "https://literature.learnche.org",
    "https://test.literature.learnche.org",
]

# Security headers. HSTS is now at one year (the policy a browser
# remembers after seeing the header once). Issue #71 staged rollout
# week 1: bumped from 300 s → 31536000 s once Caddy was confirmed
# forwarding ``X-Forwarded-Proto: https`` correctly. ``SECURE_HSTS_PRELOAD``
# stays False until a follow-up week confirms no SSL-redirect / mixed-
# content regressions; only then does ``literature.learnche.org`` get
# submitted to hstspreload.org. Override via .env still allowed for
# ad-hoc rollback (set ``SECURE_HSTS_SECONDS=0`` to clear, but expect
# returning visitors to keep the policy until their cached year expires).
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000") or "31536000")
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"

# Issue #72: full-site noindex flag, read by SecurityHeadersMiddleware.
# Set LITERATURE_NOINDEX=true in the staging .env so search engines
# leave test.literature.learnche.org alone; prod leaves it false /
# unset and uses the per-path Disallow rules in /robots.txt instead.
LITERATURE_NOINDEX = (env("LITERATURE_NOINDEX", "false") or "false").lower() in (
    "true",
    "1",
    "yes",
)

_db_keys = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "SQL_HOST", "SQL_PORT"]
_db_settings = {}
for _key in _db_keys:
    _value = env(_key)
    assert _value is not None, f"{_key} must be set via environment variable or .env file"
    _db_settings[_key] = _value

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _db_settings["POSTGRES_DB"],
        "USER": _db_settings["POSTGRES_USER"],
        "PASSWORD": _db_settings["POSTGRES_PASSWORD"],
        "HOST": _db_settings["SQL_HOST"],
        "PORT": _db_settings["SQL_PORT"],
        "CONN_MAX_AGE": 60,
    }
}
