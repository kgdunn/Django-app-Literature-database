"""Local-development settings: Postgres + DEBUG=True + runserver-friendly hosts.

Mirrors prod's database backend (Postgres) so the dev stack exercises the
same SQL paths the production stack will: the `pg_trgm` migration, the
`SearchVector` / `SearchRank` / `TrigramSimilarity` queries in
`pages.search`, and (later) the pgvector extension in Phase 12. The
connection params are read from the same env vars as prod
(`POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `SQL_HOST` /
`SQL_PORT`), but **default** to local-friendly values so a freshly
cloned checkout boots without a hand-written `.env` once a local
Postgres role + database exist.

To bootstrap the local DB once:

    sudo -u postgres psql -c "CREATE USER literature WITH PASSWORD 'literature';"
    sudo -u postgres psql -c "CREATE DATABASE literature OWNER literature;"

Phase 7 will add a `docker-compose.yml` that brings up Postgres in a
container so local dev no longer requires a host-installed Postgres.
"""

from .base import *  # noqa: F401,F403
from .base import TEMPLATES, env, env_list

DEBUG = True

TEMPLATES[0]["OPTIONS"]["debug"] = DEBUG

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "literature"),
        "USER": env("POSTGRES_USER", "literature"),
        "PASSWORD": env("POSTGRES_PASSWORD", "literature"),
        "HOST": env("SQL_HOST", "127.0.0.1"),
        "PORT": env("SQL_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
