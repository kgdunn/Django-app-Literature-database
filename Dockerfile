# syntax=docker/dockerfile:1.7

# ---- builder ------------------------------------------------------------
# Two-stage build keeps the runtime image small: the builder stage installs
# uv + the resolved venv from `uv.lock`, the runtime stage copies just the
# venv (no uv binary, no apt build deps).
#
# Both stages pin the multi-arch manifest list digest of `python:3.14-slim`
# so a Docker Hub repoint can't land silently on the next deploy. Same
# digest as the openmv stack uses — same image bytes, no double pull.
# Dependabot (`docker` ecosystem in `.github/dependabot.yml`) opens weekly
# bump PRs; CI catches breakage before merge. Issue #70.
FROM python:3.14-slim@sha256:1697e8e8d39bf168e177ac6b5fdab6df86d81cfc24dae17dfb96cfc3ef76b4dd AS builder

# Pinned to a specific uv version so a malicious push to ghcr.io/astral-sh/uv
# can't land in our build. Bump in lockstep with `uv self update` and the host
# `.python-version` if the Python target changes.
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ---- runtime ------------------------------------------------------------
FROM python:3.14-slim@sha256:1697e8e8d39bf168e177ac6b5fdab6df86d81cfc24dae17dfb96cfc3ef76b4dd AS runtime

# `libpq5` is required by `psycopg2-binary` at runtime (it ships its own
# wheel but still wants the system libpq.so.5). `curl` is only here for the
# HEALTHCHECK below; remove it to shave a few MB if a healthcheck rewrite
# ever lands.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app . .

# WORKDIR created /app as root-owned. The COPY --chown above sets ownership
# on the copied contents, but not on /app itself. Make the working directory
# writable by the runtime user so `manage.py collectstatic` (run on container
# start) can write into /app/static when the bind mount isn't pre-populated.
RUN chown app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

# Liveness probe: hits the @no-cache /healthz view in `pages.urls`. `-f` so
# any 5xx still fails the check (curl exits non-zero on HTTP errors only when
# `-f` is set). 30 s × 3 retries ⇒ container flips to `(unhealthy)` within
# ~90 s of gunicorn going dark.
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["gunicorn", "literature.wsgi:application", "--bind", "0.0.0.0:8000"]
