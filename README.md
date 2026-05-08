# Literature catalogue

The Django site behind <https://literature.learnche.org> — a personal literature catalogue: journal publications, books, conference proceedings, and theses, with authors, tags, and (where licensing permits) downloadable PDFs.

Originally written in 2010 against Django 1.x / Python 2 with django-haystack on Whoosh/Xapian, the site went defunct mid-2010s. As of 2026 it is being revived and modernized in stages on Django 5.2 / Python 3.11 / Postgres / Docker Compose, on the same Hetzner VPS that runs <https://openmv.net>. Sister repo `kgdunn/Django-dataset-download-app` is the architectural template — repo layout, settings split, Dockerfile, CI/CD workflows, and backup script are ported from there.

The site lets visitors:

- Browse every literature item in a sortable list.
- Filter by tag, author, journal, or publication year.
- Read a per-item detail page with full citation, abstract, links to DOI / external sources, and (if licensed) a PDF download.
- Search across titles, abstracts, and author names with fuzzy matching (Postgres FTS + `pg_trgm`; semantic and instant-typing search are queued).

## Layout

```
.
├── manage.py
├── Makefile                  # dev tasks (install, migrate, test, lint, debug, docker-up, ...)
├── pyproject.toml            # uv-managed dependencies + pytest config
├── uv.lock                   # committed lockfile (added in Phase 1 once deps resolve)
├── Dockerfile                # multi-stage image (Phase 7)
├── docker-compose.yml        # local dev (Postgres sidecar + runserver) — Phase 7
├── docker-compose.prod.yml   # production (Postgres, gunicorn) — Phase 7
├── .github/workflows/        # ci.yml + deploy.yml + release.yml — Phase 8/9/15
├── literature/               # Django project (settings, root URLs, WSGI)
│   ├── settings/             # base.py + dev.py + prod.py + ci.py — Phase 2
│   ├── urls.py
│   └── wsgi.py
├── items/                    # literature catalogue (Item + JournalPub/Book/ConferenceProceeding/Thesis)
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   ├── migrations/
│   ├── templates/items/
│   └── templatetags/         # `sanitise_markup` filter — Phase 5
├── tagging/                  # home-grown Tag model
├── pagehit/                  # privacy-respecting view counter
├── pages/                    # front page, about, search
│   └── templates/pages/
├── kg/                       # knowledge graph (citations, co-authorship) — Phase 13
├── templates/                # base.html + 404/500
├── utils/                    # helpers (unique_slugify, ensuredir, ...)
├── .pre-commit-config.yaml
├── .flake8
├── .gitignore
├── .env.example              # copy to .env and fill in
├── README.md
├── CLAUDE.md                 # repo orientation + revival roadmap
└── LICENSE
```

The revival is a multi-PR effort tracked in [CLAUDE.md](CLAUDE.md). Phases not yet landed are noted in the layout above.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- PostgreSQL 16 (both dev and prod use Postgres so the FTS / pgvector code paths are exercised identically; create a local `literature` user + database first — see below).

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`.

## Local development

### Native (uv)

```bash
# 1. Clone and enter the repo.
git clone https://github.com/kgdunn/Django-app-Literature-database.git literature
cd literature

# 2. Bootstrap a local Postgres role + database (one-time; PostgreSQL 16
#    must be installed and running). Match the defaults baked into
#    .env.example so a fresh checkout boots without further config.
sudo -u postgres psql -c "CREATE USER literature WITH PASSWORD 'literature';"
sudo -u postgres psql -c "CREATE DATABASE literature OWNER literature;"

# 3. Install Python deps + write a .env with a real SECRET_KEY.
uv sync --dev
cp .env.example .env
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))" \
    | tee -a .env >/dev/null
sed -i.bak '/^SECRET_KEY=change-me$/d' .env && rm .env.bak

# 4. Run migrations + the dev server.
make debug                 # collectstatic + migrate + createcachetable + runserver:8080
```

### Docker compose (Phase 7+)

```bash
cp .env.example .env       # set SECRET_KEY
make docker-up             # builds + runs Postgres + runserver in sidecars
```

Both paths target <http://127.0.0.1:8080/>. To rehearse the production stack locally (Postgres + gunicorn + `literature.settings.prod`), use `docker compose -f docker-compose.prod.yml up --build` (Phase 7+).

Create a superuser with `uv run python manage.py createsuperuser` (native) or `docker compose exec web python manage.py createsuperuser` (Docker) to log into `/admin/` and add Items, Authors, Tags.

## Testing & CI

- `make test` — runs `uv run pytest`. Smoke tests land in Phase 8.
- `make lint` — runs `pre-commit run --all-files`.
- `.github/workflows/ci.yml` (Phase 8+) runs both on every PR and on pushes to `main`, against a `postgres:16-alpine` service container.

## Production notes

Once Phase 9 lands the production stack runs at `literature.learnche.org` on the same Hetzner VPS as openmv.net. `DJANGO_SETTINGS_MODULE=literature.settings.prod` selects PostgreSQL via `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SQL_HOST`, `SQL_PORT` from the environment (or `.env`) and turns off `DEBUG`. Settings read process environment first, then fall back to `.env`.

`ALLOWED_HOSTS` reads from the `ALLOWED_HOSTS` env var (comma-separated). Defaults: `.literature.learnche.org,127.0.0.1` in prod, `127.0.0.1,localhost` in dev. Override the env var to deploy under a different hostname.

PDFs land in `BASE_DIR / 'media' / 'literature' / 'pdf' / <slug[0]> / <slug>.pdf`. Caddy serves `/media/` and `/static/` directly from bind-mounted host directories; `download_item` streams the PDF body via `FileResponse` (after Phase 5) to dodge Cloudflare's Bot Fight Mode false-positives.

The `PageHit` table grows with every page view. After Phase 4 lands it holds only `(item, item_pk, datetime, extra_info)` — no IP, user-agent, or referrer is stored.

## Tooling

- `make install` — `uv sync --dev`.
- `make migrate` — `uv run python manage.py migrate`.
- `make collectstatic` — `uv run python manage.py collectstatic --no-input`.
- `make test` — `uv run pytest`.
- `make lint` — `uv run pre-commit run --all-files`.
- `make debug` — collectstatic + migrate + createcachetable + runserver on `:8080`.
- `make docker-up` / `make docker-down` — wrappers over `docker compose` (Phase 7+).
- `make clean` — remove `__pycache__`, caches, etc.

## License

BSD 2-Clause — see [LICENSE](LICENSE). © 2010–present Kevin Dunn.

## Contributing / roadmap

See [CLAUDE.md](CLAUDE.md) for an architectural overview, the revival status table, and the prioritised list of phases still to land.
