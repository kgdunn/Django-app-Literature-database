# Literature catalogue

The Django site behind <https://literature.learnche.org> — a personal literature catalogue: journal publications, books, conference proceedings, and theses, with authors, tags, and (admin-only) PDFs used for full-text indexing.

The site lets visitors:

- Browse every literature item in a sortable, mobile-responsive table.
- Filter items by tag, author, journal, or publication year.
- Read a per-item detail page with full citation, abstract (with `\(...\)` LaTeX rendered via MathJax), DOI / external link, and tags-as-chips.
- Search across titles, abstracts, and the (admin-extracted) full PDF text. Author last-name typos are matched fuzzily via Postgres `pg_trgm` similarity. Each query increments a privacy-respecting hit counter (timestamp + query only — no IP, user-agent, or referrer is stored).

PDFs are uploaded by the admin and **never exposed for download** (copyright restriction); they are consumed only by an admin-only `__extract_extra__` endpoint that runs `pdfplumber` to extract plain text into the FTS search vector.

## Layout

```
.
├── manage.py
├── Makefile                  # dev tasks (install, migrate, test, lint, debug, docker-up, sri, ...)
├── pyproject.toml            # uv-managed dependencies + pytest config
├── uv.lock                   # committed lockfile
├── Dockerfile                # multi-stage image (uv builder + python:3.11-slim runtime)
├── docker-compose.yml        # local dev (Postgres sidecar + runserver, hot-reload)
├── docker-compose.prod.yml   # production (Postgres + gunicorn, loopback-only on :8002 / :5435)
├── bin/
│   └── deploy-impl.sh        # Hetzner-side deploy script (run via SSH forced-command)
├── .github/
│   ├── workflows/ci.yml      # pre-commit + pytest + pip-audit on push and PR
│   ├── workflows/deploy.yml  # auto-deploy to Hetzner on push to main
│   └── dependabot.yml        # weekly bumps for github-actions + docker
├── literature/               # Django project (settings, root URLs, WSGI/ASGI, middleware)
│   ├── settings/             # base.py + dev.py + prod.py + ci.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   ├── middleware.py         # SecurityHeadersMiddleware (CSP, Permissions-Policy, COOP)
│   └── context_processors.py
├── items/                    # literature catalogue (Item + JournalPub / Book / ConferenceProceeding / Thesis)
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── apps.py
│   ├── migrations/
│   ├── templates/items/      # entries_list.html, item.html, _item_row.html, show-tag-cloud.html
│   ├── templatetags/         # `sanitise_markup` (bleach) + `cloud` / `most_viewed` / `most_searched`
│   └── tests/                # conftest fixtures + test_models + test_views (35 tests)
├── tagging/                  # home-grown Tag model
├── pagehit/                  # privacy-respecting view counter (no UA / IP stored)
├── pages/                    # front page, about, search, healthz
│   └── templates/pages/      # base.html lives at top-level templates/, this dir has the pages-specific ones
├── utils/                    # ensuredir, get_IP_address (logging only), paginated_queryset, unique_slugify
├── templates/                # base.html, 404.html, 500.html
├── docs/
│   ├── deploy.md             # Hetzner host bootstrap runbook (Cloudflare DNS + Origin Cert + Caddy + SSH)
│   └── legacy-todo.md        # 2010-era todo.txt archive, mapped to revival phases
├── .pre-commit-config.yaml
├── .flake8
├── .editorconfig
├── .python-version           # 3.11
├── .gitignore
├── .dockerignore
├── .env.example              # copy to .env and fill in
├── README.md
├── CLAUDE.md                 # repo orientation + revival roadmap
└── LICENSE
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- PostgreSQL 16 (both dev and prod use Postgres so the FTS / `pg_trgm` / pgvector code paths are exercised identically). Docker Compose can run Postgres as a sidecar so a host install is **not** required.

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`.

## Local development

### Native (uv)

This path runs `runserver` natively against a host-installed Postgres. If you'd rather keep Postgres in a container, use the Docker compose path below — it's strictly simpler and avoids the host-Postgres bootstrap.

```bash
# 1. Clone and enter the repo
git clone https://github.com/kgdunn/Django-app-Literature-database.git literature
cd literature

# 2. Bootstrap a local Postgres role + database (one-time; PostgreSQL 16
#    must be installed and running on the host). Match the defaults baked
#    into .env.example so a fresh checkout boots without further config.
sudo -u postgres psql -c "CREATE USER literature WITH PASSWORD 'literature' CREATEDB;"
sudo -u postgres psql -c "CREATE DATABASE literature OWNER literature;"

# 3. Install Python deps + write a .env with a real SECRET_KEY.
uv sync --dev
cp .env.example .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))" \
    | tee -a .env >/dev/null
sed -i.bak '/^SECRET_KEY=change-me$/d' .env && rm .env.bak

# 4. Run migrations + the dev server (collectstatic + migrate + createcachetable + runserver:8080)
make debug
```

The `CREATEDB` privilege on the `literature` Postgres user is needed so `pytest`'s test runner can spin up a `test_literature` database (see *Testing & CI* below).

### Docker compose

No host Postgres install required — the compose file ships a `postgres:16-alpine` sidecar.

```bash
cp .env.example .env       # set SECRET_KEY (Postgres defaults are fine for dev)
make docker-up             # builds + runs Postgres + runserver in sidecars
```

Both paths use `literature.settings.dev` and serve <http://127.0.0.1:8080/>. To rehearse the production stack locally (Postgres + gunicorn + `literature.settings.prod` on offset loopback ports `:8002` / `:5435`), use `docker compose -f docker-compose.prod.yml up --build` instead.

Create a superuser with `uv run python manage.py createsuperuser` (native) or `docker compose exec web python manage.py createsuperuser` (Docker) to log into `/admin/` and add Items / Authors / Tags.

## Testing & CI

- `make test` — runs the smoke-test suite (`uv run pytest`).
- `make lint` — runs `pre-commit run --all-files`.
- `.github/workflows/ci.yml` runs both on every PR and on pushes to `main`, against a `postgres:16-alpine` service container.

## Production notes

Production runs at `https://literature.learnche.org` on the same Hetzner VPS as `openmv.net`. Caddy (host-installed, shared) terminates TLS via a Cloudflare Origin Certificate; the literature stack itself is two Docker containers bound to loopback (`127.0.0.1:8002` for gunicorn, `127.0.0.1:5435` for Postgres). Auto-deploy is wired through `.github/workflows/deploy.yml` — every push to `main` SSHes to Hetzner via a forced-command key and runs `bin/deploy-impl.sh`.

The full host-bootstrap runbook (Cloudflare DNS, Origin Cert, Caddy server block, SSH deploy key, GitHub repo secrets) lives in [`docs/deploy.md`](docs/deploy.md).

Highlights worth knowing before deploying:

- `DJANGO_SETTINGS_MODULE=literature.settings.prod` (forced by `docker-compose.prod.yml`'s `web.environment` block) selects PostgreSQL via `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SQL_HOST`, `SQL_PORT` from `.env` and turns off `DEBUG`. Settings read process environment first, then fall back to `.env`.
- `ALLOWED_HOSTS` reads from the `ALLOWED_HOSTS` env var (comma-separated). Defaults: `.literature.learnche.org,127.0.0.1` in prod, `127.0.0.1,localhost` in dev.
- Static files land in `BASE_DIR / 'static'` (host-side `data/static/`) after `collectstatic`. Admin-uploaded PDFs land in `BASE_DIR / 'media'` (host-side `data/media/`). Caddy serves `/static/` directly off disk; **`/media/literature/pdf/*` is explicitly 404'd** at the Caddy layer (copyright — Phase 5 rule). Locally, `runserver` only serves `/media/` when `DEBUG=True`.
- The `PageHit` table grows with every request. There is no automatic pruning; the schema holds no PII (Phase 4) so unbounded growth is privacy-safe.

## Tooling

- `make install` — `uv sync --dev`.
- `make migrate` — `uv run python manage.py migrate`.
- `make collectstatic` — `uv run python manage.py collectstatic --no-input`.
- `make test` — `uv run pytest`.
- `make lint` — `uv run pre-commit run --all-files`.
- `make debug` — collectstatic + migrate + createcachetable + runserver on `:8080`.
- `make docker-up` / `make docker-down` — wrappers over `docker compose` (dev compose).
- `make sri` — recompute Subresource Integrity hashes for the CDN scripts in `templates/base.html`.
- `make clean` — remove `__pycache__`, caches, etc.

## License

BSD 2-Clause — see [LICENSE](LICENSE). © 2010–present Kevin Dunn.

## Contributing / roadmap

See [CLAUDE.md](CLAUDE.md) for an architectural overview, the revival status table, and the prioritised list of phases still to land.
