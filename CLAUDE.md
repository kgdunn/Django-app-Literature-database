# CLAUDE.md

Orientation for Claude Code (and any other future maintainer) working in this repository. Keep this file up-to-date as the codebase evolves.

## What this repo is

The Django site behind <https://literature.learnche.org> — a personal literature catalogue: journal publications, books, conference proceedings, and theses, with authors, tags, and (where licensing permits) downloadable PDFs. Originally written in 2010 against Django 1.x / Python 2 with django-haystack on Whoosh/Xapian, it went defunct mid-2010s. As of 2026 it is being revived and modernized in stages: Django 5.2 / Python 3.11 / Postgres / Docker Compose on Hetzner, on the same VPS as <https://openmv.net>, behind the same Caddy + Cloudflare stack.

The sister project at `kgdunn/Django-dataset-download-app` (openmv.net) is the architectural template for this revival — repo layout, settings split, Dockerfile, CI/CD workflows, backup script, and security middleware are all ported from there.

**Revival status** — this section is the authoritative tracker; update it on every PR that lands a phase. Phases are defined in `/root/.claude/plans/we-have-this-code-validated-brooks.md` (the original revival plan) and re-summarized in `RELEASES.md`.

| Phase | Title                                                | Status   |
| ----- | ---------------------------------------------------- | -------- |
| 0     | Repo hygiene baseline (this file, pyproject, Makefile) | in progress |
| 1     | Python 2 → 3 + Django 1.11 → 5.2 port                | pending  |
| 2     | Settings split + middleware + .env.example           | pending  |
| 3     | Drop Haystack, add Postgres FTS (Stage 1 search)     | pending  |
| 4     | Trim PageHit (drop UA/IP) + drop IP gate on download | done     |
| 5     | Modernize PDF download + bleach sanitisation         | pending  |
| 6     | Templates modernization (Bootstrap, MathJax, mobile) | pending  |
| 7     | Dockerize (Dockerfile + compose dev/prod)            | pending  |
| 8     | Tests + CI workflow                                  | pending  |
| 9     | Hetzner provisioning + deploy workflow               | pending  |
| 10    | Data import from legacy dump                         | pending  |
| 11    | S3 nightly backups                                   | pending  |
| 12    | pgvector semantic search (Stage 2)                   | pending  |
| 13    | Knowledge graph (citations, co-authorship)           | pending  |
| 14    | Meilisearch sidecar (Stage 3)                        | pending  |
| 15    | RELEASES.md + release workflow                       | pending  |

The site is **not yet in production** at the time of writing — there is no live `literature.learnche.org` to break. Once Phase 9 lands the staging hostname `test.literature.learnche.org` is the rehearsal target; once Phase 11 lands the apex flips live and the openmv-style "live site cannot break" rule applies.

## Project shape

- **Project**: `literature/` (settings package, URL conf, WSGI/ASGI). Settings live under `literature/settings/` — `base.py` (shared), `dev.py` (local Postgres + DEBUG=True), `prod.py` (Postgres + DEBUG=False + Caddy proxy headers + HSTS + secure cookies), `ci.py` (GitHub Actions — derives from `prod.py` and disables HTTPS-only middleware so the Django test client works). Both `dev` and `prod` target Postgres so the search/FTS/pgvector code paths are exercised the same way locally and in production; the only behavioural difference is `DEBUG`, `ALLOWED_HOSTS`, and the proxy/secure-cookie flags.
- **Apps**:
  - `items/` — the literature catalogue itself.
  - `tagging/` — a small home-grown `Tag` model (predates django-taggit; not vendored from `django-tagging`).
  - `pagehit/` — privacy-respecting view counter (Phase 4 trimmed the historical UA/IP columns).
  - `pages/` — front page, about page, search page. Has no models.
  - `kg/` — knowledge graph (citations, co-authorship). Created in Phase 13.
- **Models**:
  - `items.Item` — abstract-ish base. Multi-table inheritance: subclasses `JournalPub`, `Book`, `ConferenceProceeding`, `Thesis` each create their own DB table joined to `Item` via an implicit OneToOne. Item fields: `title`, `slug`, `item_type` (`thesis|journalpub|book|conferenceproc`), `year`, `doi_link`, `web_link`, `abstract`, `show_abstract`, `date_created` (`auto_now=True`), `pdf_file` (`upload_to=literature/pdf/{slug[0]}/{slug}.pdf`), `private_pdf`, `can_show_pdf`, `other_search_text` (free-text search bucket — auto-extracted from PDF or hand-curated). Custom manager `LatestItemManager` orders by `-date_created`.
  - `items.Author` — `first_name`, `middle_initials`, `last_name`, `slug` (auto-generated via `utils.unique_slugify`).
  - `items.AuthorGroup` — through-table for `Item.authors` M2M, carries `order` (IntegerField) so author position is preserved.
  - `items.School`, `items.Journal`, `items.Publisher` — lookup tables, all with `name` + auto-`slug`.
  - `items.JournalPub` — adds FK `journal`, `volume`, `page_start`, `page_end`. `full_citation()` returns HTML.
  - `items.Book` — adds FK `publisher`, M2M `editors`, `volume`, `series`, `edition`, `isbn`.
  - `items.ConferenceProceeding` — adds M2M `editors`, `conference_name`, `page_start`/`page_end`, `organization`, `location`, FK `publisher` (nullable).
  - `items.Thesis` — adds `thesis_type` (`masters|phd`), FK `school`, M2M `supervisors`.
  - `tagging.Tag` — `slug` (unique, auto-generated), `name`, `description`. Reverse M2M from `Item.tags`.
  - `pagehit.PageHit` — holds only `(item, item_pk, datetime, extra_info)` after Phase 4 dropped the legacy `ua_string` and `ip_address` columns (migration `0003_drop_pagehit_pii`). Two columns power the visible features: top-N most-viewed lists and the per-item view count on the detail page. Rows are kept indefinitely; the schema itself no longer holds any user-identifying data so retention is privacy-safe.
  - `kg.Citation`, `kg.ExternalReference`, `kg.CoauthorshipEdge` — Phase 13.

- **Views** (`items/views.py`, `pages/views.py`):
  - `pages.front_page` — `/` — homepage. Renders 10 latest items + a search box.
  - `pages.about_page` — `/about` — static about page.
  - `pages.search` — `/search?q=<terms>` — search results. After Phase 3, this is the canonical Postgres-FTS endpoint (whitespace-AND tokens, weighted `SearchVector` over title/abstract/other_search_text + `TrigramSimilarity` for fuzzy author matching). Pre-Phase 3, this is a Haystack passthrough. Empty / missing `q` returns the front page.
  - `items.show_items` — `/item/show-all`, `/item/<view>/<slug>/`, `/item/pub-by-year/<year>/` — paginated list view, parameterized by `what_view` (`all`, `tag`, `author`, `journal`, `pub-by-year`, `sort`).
  - `items.view_item` — `/item/<id>/<slug>` (slug optional) — detail page.
  - `items.download_item` — `/item/<id>/download.pdf` — increments a `PageHit` row, then writes the file body into an `HttpResponse`. Phase 4 dropped the legacy IP-allowlist gate; only the per-item `Item.private_pdf` flag still gates access. Phase 5 will tighten the URL regex before the DB lookup and stream via `FileResponse` to dodge Cloudflare's Bot Fight Mode false-positives (matching openmv's hardening from openmv#86).
  - `items.__extract_extra__` — admin-only endpoint that runs the PDF text extractor (`pdfplumber` after Phase 1; `pdfminer` before) and writes the result into `Item.other_search_text`.

- **Templates** (`templates/` + per-app `{app}/templates/{app}/`):
  - `templates/base.html` — site layout. After Phase 6, Bootstrap 3 inline-style (no static-file dependency, MathJax CDN for `\(...\)` LaTeX in abstracts, ECharts CDN for the per-item view sparkline). Pre-Phase-6 is the legacy markup.
  - `templates/404.html`, `templates/500.html` — error pages.
  - `pages/templates/pages/front-page.html` — homepage.
  - `pages/templates/pages/about-page.html` — about.
  - `items/templates/items/show-entries.html`, `entries_list.html`, `item.html`, `show-tag-cloud.html` — list, detail, and tag-cloud renderings.
  - `templates/search/*` — Haystack-era search templates, **deleted in Phase 3** (the `pages.search` view will render directly into a new `pages/templates/pages/search.html`).

- **Custom template tags**: `items/templatetags/extra_tags.py` (after Phase 5) defines `sanitise_markup` (passes admin-authored HTML through `bleach` with a small allowlist before rendering — see `docs/SECURITY.md`). The bleach allowlist matches openmv's: `a, b, i, em, strong, sub, sup, code, br, p, span, ul, ol, li, dl, dt, dd`.

- **Project-local middleware**: `literature/middleware.py` (after Phase 2) defines `SecurityHeadersMiddleware`, which sets `Content-Security-Policy`, `Permissions-Policy`, and `Cross-Origin-Opener-Policy` on every response. Wired into `MIDDLEWARE` in `base.py` immediately after Django's `SecurityMiddleware`.

- **Admin**: registered in `items/admin.py`, `tagging/admin.py`, `pagehit/admin.py`. `PageHitAdmin` is read-only (`readonly_fields` covers every column, `has_add_permission` returns `False`) — the table is an append-only audit log written exclusively by `pagehit.views.create_hit`. `date_hierarchy = "datetime"` + `list_filter = ("item",)` keep the change-list scoped without loading the whole table.

## How it runs

- `make debug` runs `collectstatic --no-input`, `migrate`, `createcachetable`, then `runserver 8080 --nostatic`.
- Settings read **process environment first**, then fall back to a `.env` file via `python-dotenv` if one exists (Phase 2+). The `env()` and `env_list()` helpers in `literature/settings/base.py` encapsulate this. `SECRET_KEY` is the only universally required key; `prod.py` additionally requires the `POSTGRES_*` + `SQL_*` keys. Either layer (env or `.env`) can supply them — handy for containers, CI, and ad-hoc overrides.
- Which DB / hosts / DEBUG flag you get depends on `DJANGO_SETTINGS_MODULE`:
  - `literature.settings.dev` (default in `manage.py`, `wsgi.py`, `asgi.py`, `pyproject.toml` pytest) → Postgres via `POSTGRES_*` + `SQL_*` keys (defaults: `literature/literature/literature@127.0.0.1:5432`), `DEBUG=True`, `ALLOWED_HOSTS` from `$ALLOWED_HOSTS` (default `127.0.0.1,localhost`).
  - `literature.settings.prod` (forced by `docker-compose.prod.yml`'s `web.environment` block) → Postgres via `POSTGRES_*` + `SQL_*` keys, `DEBUG=False`, `ALLOWED_HOSTS` from `$ALLOWED_HOSTS` (default `.literature.learnche.org,127.0.0.1`), `SECURE_PROXY_SSL_HEADER` + `CSRF_TRUSTED_ORIGINS` for Caddy.
  - `literature.settings.ci` (forced by `.github/workflows/ci.yml` for the pytest step) → re-exports prod, then turns off `SECURE_SSL_REDIRECT` / HSTS / secure-cookie flags so the Django test client (which uses HTTP) doesn't hit a 301. Same Postgres `POSTGRES_*` + `SQL_*` env vars as prod, supplied by the workflow against the `postgres:16-alpine` service.

## Running locally

Two paths:

**Native (uv):**
```bash
cp .env.example .env   # edit SECRET_KEY
uv sync --dev
make debug             # collectstatic + migrate + createcachetable + runserver:8080
```

**Docker compose (`make docker-up` — Phase 7+; will run Postgres + runserver in containers):**
```bash
cp .env.example .env   # set SECRET_KEY
make docker-up         # docker compose up --build
```

Both paths use `literature.settings.dev` and serve <http://127.0.0.1:8080/>. To rehearse the production stack (Postgres + gunicorn + `literature.settings.prod`), use `docker compose -f docker-compose.prod.yml up --build` instead.

## Production deployment (Hetzner)

Architecture (after Phase 9 lands):

```
Cloudflare (proxied, orange cloud) ──HTTPS──> Caddy on Hetzner host (TLS terminator + static)
                                                ├── /static/*          → ./data/static/  (file_server)
                                                ├── /media/*           → ./data/media/   (file_server, PDFs)
                                                ├── /robots.txt etc.   → ./data/public/
                                                └── everything else    → 127.0.0.1:8002 → gunicorn (Docker)
                                                                                          ├── postgres (Docker, 127.0.0.1:5435)
                                                                                          └── meilisearch (Docker, 127.0.0.1:7701, Phase 14)
```

- **VPS**: same Hetzner Cloud Ubuntu 24.04 host that runs openmv.net and Factori.al. The literature stack coexists via offset ports (gunicorn `:8002`, postgres `:5435` — openmv uses `:8001/:5434`) and the shared host-installed Caddy.
- **Code path**: `/home/deploy/literature/repo/` — git checkout of `main`.
- **Compose file**: `docker-compose.prod.yml` runs two services bound to loopback only — `web` (gunicorn on `127.0.0.1:8002`) and `db` (`postgres:16-alpine` on `127.0.0.1:5435`). Phase 14 adds `meilisearch` on `127.0.0.1:7701`.
- **Bind-mounted data dirs** (under `/home/deploy/literature/repo/data/`):
  - `media/` — Django uploads served by Caddy and mounted into the container as `/app/media`. **This is the PDF library — irreplaceable.** Always backed up to S3.
  - `static/` — `collectstatic` output, mounted as `/app/static`. Re-populated by the `web` container's startup command. Not backed up (regenerated).
  - `public/` — the small files Caddy aliases directly (`robots.txt`, `favicon.ico`).
- **`.env`** is loaded into the container's process environment via `env_file: .env` in `docker-compose.prod.yml`, and the same file is also bind-mounted at `/app/.env:ro`. Mirrors the openmv setup. Never commit `.env`.
- **`DJANGO_SETTINGS_MODULE=literature.settings.prod`** is set on the `web` service in `docker-compose.prod.yml`; this is what selects the prod-only DB / hosts / proxy headers.
- **Caddy config**: `/etc/caddy/Caddyfile` on the host (shared with openmv and Factori.al). Reload with `sudo systemctl reload caddy` (validate first with `sudo caddy validate --config /etc/caddy/Caddyfile`).
- **TLS**:
  - `literature.learnche.org` uses a **Cloudflare Origin Certificate** at `/etc/caddy/origin-certs/literature.learnche.org/`. Cloudflare's edge serves a public-trusted cert to visitors and re-encrypts to origin in `Full (strict)` mode. The `learnche.org` apex points at a different server entirely; only the `literature` subdomain record sits on Hetzner.
  - `test.literature.learnche.org` uses Caddy-managed Let's Encrypt. It must stay **DNS-only** (grey cloud) in Cloudflare so the HTTP/TLS challenge can reach origin directly.
- **DNS**: `learnche.org` is a Cloudflare-hosted zone. Add A/AAAA `literature` (proxied) and `test.literature` (DNS-only) pointing at the Hetzner IPs `178.104.167.195` / `2a01:4f8:1c19:2380::1`.
- **Auto-deploy**: every push to `main` fires `.github/workflows/deploy.yml`, which SSHes into Hetzner via a forced-command key and triggers `bin/deploy-impl.sh`. The deploy script runs `docker compose -f docker-compose.prod.yml up -d --build` (which in turn runs `migrate --noinput` + `collectstatic --noinput` on container start, then boots gunicorn) and sanity-curls `127.0.0.1:8002/healthz`.
- **Manual deploy** (rollback, hotfix, debugging): from `/home/deploy/literature/repo/`, run `git pull && docker compose -f docker-compose.prod.yml up -d --build` directly.

## Backups

Off-host backups go to AWS S3 — same bucket as openmv (`openmv-backups`) under prefix `literature/`, deliberately a different cloud provider / account from Hetzner so a compromise of one doesn't reach the other. The Hetzner-side script is `bin/backup-literature.sh`; it runs nightly under `deploy` from cron and does three things:

1. **Postgres dump** of the running `db` container via `docker compose -f docker-compose.prod.yml exec -T db pg_dump --clean --if-exists`, gzipped, uploaded to `s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/db/daily/db_literature-YYYY-MM-DD.sql.gz`. Same dump copied to `db/monthly/` on the 1st of each month and `db/yearly/` on Jan 1.
2. **`aws s3 sync`** of `data/media/` → `…/media/` and `data/public/` → `…/public/`. No `--delete` flag — an accidental local rm or detached bind mount must not propagate to the off-host copy. **`data/media/` is the PDF library; this is the irreplaceable bytes.** `data/static/` is intentionally **not** backed up because `collectstatic` regenerates it on every container start.
3. **Retention pruning** by S3 `LastModified`: `db/daily/` keeps 15, `db/monthly/` keeps 12, `db/yearly/` is never pruned.

S3 layout:

```
s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/
├── db/
│   ├── daily/    db_literature-2026-05-08.sql.gz   (≤15)
│   ├── monthly/  db_literature-2026-05.sql.gz      (≤12)
│   └── yearly/   db_literature-2026.sql.gz         (∞)
├── media/        mirror of data/media/
└── public/       mirror of data/public/
```

The IAM principal for these keys is scoped to the `literature/*` prefix only — same pattern as openmv but a separate prefix, so a key leak limits blast radius. Bucket versioning + SSE-S3 are on. Full step-by-step (AWS bucket + IAM, Hetzner install, smoke-test, restore drill, troubleshooting) is in [`docs/backup.md`](docs/backup.md) once Phase 11 lands.

Cron entry (run as `deploy`):

```
35 22 * * *  /home/deploy/literature/repo/bin/backup-literature.sh \
    >> /home/deploy/literature/backups/backup.log 2>&1
```

The 22:35 schedule is intentionally one hour offset from openmv's 21:35 to spread S3 upload load. The script is *not* installed automatically by `bin/deploy-impl.sh`; cron lives outside the repo because its presence and schedule are operational state, not application state.

Meilisearch (Phase 14+) is **not** backed up — its index is rebuildable from Postgres via `manage.py reindex_meilisearch`. Document in CLAUDE.md if that ever changes.

## Search architecture

Three stages, layered:

1. **Postgres FTS** (Phase 3 — Stage 1, canonical) — `pages.search` builds a weighted `SearchVector` over `Item.title` (A), `Item.abstract` (B), `Item.other_search_text` (C), ranked with `SearchRank`, OR-joined with `__trigram_similar` on author last names for fuzzy author matching. Uses `SearchQuery(..., search_type='websearch')` so bare terms AND, quoted phrases preserve order, and `-foo` excludes. Backed by `CREATE EXTENSION IF NOT EXISTS pg_trgm` (`items` migration `0004_pg_trgm`). No GIN index yet — the corpus is small enough that a sequential scan is sub-100 ms; revisit in Phase 9/10 if benchmarks demand it.

2. **pgvector** (Phase 12 — Stage 2, semantic) — `Item.embedding` (`vector(N)`, dimension TBD by model choice). HNSW index. Embeddings produced in batch via an external API (Voyage / OpenAI / similar — model decided when Phase 12 PR opens). `manage.py rebuild_embeddings --batch-size 100` is idempotent and resumable. Detail page surfaces a "Similar papers" panel via `Item.objects.exclude(pk=item.pk).order_by(L2Distance("embedding", item.embedding))[:5]`.

3. **Meilisearch sidecar** (Phase 14 — Stage 3, instant-typing UX) — `meilisearch:v1.x` container on `127.0.0.1:7701`. `manage.py reindex_meilisearch` batch-pushes Item documents (title, abstract, authors[], tags[], year, journal). Triggered on save via a Django signal. The front-page search box becomes as-you-type via a small Django proxy view (master key never leaves the server). Postgres FTS remains the canonical fallback for `?q=` deep-link URLs.

Until Phase 3 lands the search path is the legacy Haystack/Whoosh/Xapian stack, which is broken on modern Python. Don't try to fix Haystack — replace it.

## Knowledge graph (Phase 13)

`kg/` app with `Citation(source: FK Item, target: FK Item)` for known-local edges and `ExternalReference(item: FK Item, openalex_id, doi, title)` for cited works that aren't in the local corpus. `manage.py enrich_from_openalex` walks every `Item` with a DOI, pulls its references from OpenAlex (Crossref as fallback), matches to local Items by DOI, and inserts edges. `CoauthorshipEdge(author_a, author_b, weight)` is a materialized view refreshed nightly from `AuthorGroup`. Detail-page panels surface "References" (outgoing edges) and "Cited by" (incoming).

## Gotchas worth knowing before editing

1. **Multi-table inheritance on `Item`.** `JournalPub`, `Book`, `ConferenceProceeding`, `Thesis` each have their own DB table joined to `Item` via an implicit OneToOne. `Item.objects.all()` returns the parent rows; `JournalPub.objects.all()` joins. When iterating in templates, use the typed model if you need the subclass-specific fields (`full_citation()` differs per subclass). Avoid `Item.objects.select_subclasses()` patterns — the codebase doesn't use `django-model-utils` and there's no need for it; the subclass is reachable via `item.journalpub`/`item.book`/etc. when `item.item_type` says so.

2. **Legacy `media/` prefix on `Item.pdf_file`.** Pre-revival data may have stored paths as `media/literature/pdf/<slug>.pdf`. The new `upload_to` builds `literature/pdf/<slug[0]>/<slug>.pdf` (no `media/`). The Phase 10 import script strips the prefix; if you ever re-restore from a stale legacy dump, re-run: `UPDATE items_item SET pdf_file = regexp_replace(pdf_file, '^media/', '') WHERE pdf_file LIKE 'media/%';`

3. **`Item.private_pdf` and `Item.can_show_pdf` are independent flags.** `can_show_pdf=True AND private_pdf=False AND <pdf_file exists>` is the only combination that exposes a download URL. Templates and `download_item` both check this. Phase 4 dropped the IP-allowlist gate that had stacked on top (it didn't compose with Cloudflare's edge-IP rewrite anyway), so `private_pdf` is now the only ACL on download_item. **Phase 5 decision pending**: openmv's all-public model is simpler; consider dropping `private_pdf` entirely. If retained, document why in `docs/SECURITY.md`.

4. **`download_item` validates its `file_name` against a tight regex before any DB lookup** (after Phase 5). Anything outside that shape returns 404, not 500. The pre-Phase-5 path 302-redirected to `/media/...` and is broken behind Cloudflare's Bot Fight Mode (issue openmv#86). Stream via `FileResponse` after Phase 5; the file just needs to be readable by the gunicorn worker — in production via the `/app/media` bind mount, locally via `BASE_DIR/media/`. Caddy's `/media/*` `file_server` rule stays in place for any externally-cached direct links.

5. **Admin-authored markup in `Item.abstract` and (Author / Tag) `description` is passed through `bleach` at render time** by the `sanitise_markup` filter (after Phase 5). Tags outside the allowlist (script, iframe, style, event handlers, javascript: URLs) are stripped. LaTeX in `\(...\)` survives because bleach treats backslashes and dollar signs as text. If you add a new field that should accept the same markup, route it through the same filter — don't reach for `|safe`.

6. **`PageHit` table privacy.** Pre-Phase-4 the schema held `ua_string` and `ip_address`. Migration `pagehit/0003_drop_pagehit_pii` destroyed those columns, taking every existing value with them. There is no retention job because the schema itself no longer holds PII. If you ever restore a pre-Phase-4 backup, re-run `manage.py migrate` to re-trim it. `pagehit.views.create_hit` is the sole writer; the admin is read-only.

7. **`literature.urls` mounts `items.urls` as `r'item/'`** (no leading `^`). That technically matches `r'item/'` *anywhere* in the path, but Django's URL resolver is greedy from the start of `path_info`, so it works in practice. Don't tighten this without checking the legacy URL patterns above it.

8. **`literature.urls` mounts `pages.urls` as `r''`** (empty regex — also matches anywhere). The `pages.urls` patterns each anchor with `^`, so it only catches the routes that anchor. Any new top-level URL must go through `pages.urls`, not a direct mount in `literature.urls`, to keep this convention.

9. **`from local_settings import *` at the bottom of legacy `settings.py`** is a Python 2-style relative import that's broken on Python 3. Phase 1 + Phase 2 jointly remove this — the env-driven settings split makes `local_settings.py` redundant. If a legacy `local_settings.py` exists in a deploy, delete it.

10. **`Item.author_slugs` (legacy) calls `unicode()` and uses an `.encode('ascii', 'ignore')` chain.** This breaks on Python 3 (`unicode` is undefined). Phase 1 rewrites it to use `unicodedata.normalize("NFKD", ...).encode("ascii", "ignore").decode("ascii")` and `str()`. Don't restore the old form.

11. **`ForeignKey(...)` without `on_delete=` is a Django 2.0+ error.** Several legacy FKs (`AuthorGroup.author`, `AuthorGroup.item`, `JournalPub.journal`, `Book.publisher`, `Thesis.school`, `ConferenceProceeding.publisher`) need `on_delete=` added in Phase 1. Use `models.PROTECT` for `Author`/`Journal`/`Publisher`/`School` (lookup tables — deletion shouldn't cascade) and `models.CASCADE` for `AuthorGroup` (a join row owned by its `Item`).

12. **`from django.core.urlresolvers import reverse` is removed in Django 4.0.** Phase 1 swaps every occurrence (mainly `items/models.py`) for `from django.urls import reverse`.

13. **Haystack legacy paths.** `search_sites.py`, `items/search_indexes.py`, `templates/search/`, and the `'haystack'` entry in `INSTALLED_APPS` are all deleted in Phase 3. The `pages.search` view name `haystack_search` is preserved as a URL `name` so `{% url 'haystack_search' %}` in templates keeps working — the *view body* is rewritten, not the route name.

14. **`Item.doi_link_cleaned` calls `.lstrip('http://dx.doi.org/')`** which is a per-character strip, not a prefix strip. `.lstrip("hp:/dx.oirg")` would do the same thing. This is a latent bug; if a DOI happens to start with any of those characters (e.g. `10.1234`) it'll be eaten. Fix to `removeprefix("https://dx.doi.org/").removeprefix("http://dx.doi.org/").removeprefix("https://doi.org/").removeprefix("http://doi.org/")` in Phase 1 cleanup.

15. **Security review of the codebase lives in `docs/SECURITY.md`** (created in Phase 5) — that's the canonical record of every audit finding (fixed and deferred), the host-side recommendations (Caddy admin rate-limit, Cloudflare WAF, fail2ban), and the follow-up issues. Update it on any PR that touches a security-relevant surface.

## Tooling

- **Dependencies** are managed with [uv](https://docs.astral.sh/uv/). The source of truth is `pyproject.toml` + the committed `uv.lock`. There is no `requirements.txt`.
  - Install everything: `uv sync --dev`
  - Add a runtime dep: `uv add <pkg>`; dev dep: `uv add --dev <pkg>`
  - Refresh the lockfile after manual edits: `uv lock`
  - Audit installed deps for known CVEs: `uv run pip-audit` (added to dev group; CI runs it non-blocking).
  - Django is pinned `>=5.2,<5.3` (5.2 is the current LTS series; this project tracks LTS releases only).
  - Runtime deps include `bleach` for HTML sanitisation (Phase 5+) and `pdfplumber` for PDF text extraction (Phase 1+, replaces the legacy `pdfminer`).
- **Tests** run with `uv run pytest` (or `make test`). `pytest-django` is wired through `[tool.pytest.ini_options]` in `pyproject.toml`. Smoke suite lives in `items/tests/test_views.py` (Phase 8+).
- **GitHub Actions** runs `pre-commit run --all-files` and `pytest` on every PR and on push to `main` (`.github/workflows/ci.yml`, Phase 8). The pytest step boots a `postgres:16-alpine` service container, sets `DJANGO_SETTINGS_MODULE=literature.settings.ci`, and injects `SECRET_KEY` + `POSTGRES_*` + `SQL_*` env vars directly via the workflow `env:` block — no `.env` file is created. Tests run against the same database engine as production.
- **Docker compose**: `docker-compose.yml` is for **local development** (volume-mounts the source for hot reload, runs `runserver` against a sidecar Postgres container via `literature.settings.dev`). `docker-compose.prod.yml` is the **production** compose used on Hetzner (bind-mounts `.env` and `data/` dirs, sets `DJANGO_SETTINGS_MODULE=literature.settings.prod`, runs `migrate` + `collectstatic` + `gunicorn`, binds to loopback on offset ports `8002`/`5435`). Both use the same `Dockerfile`. (Compose files land in Phase 7.)
- **pre-commit** is configured (`.pre-commit-config.yaml`) — same hook set as openmv (`pre-commit-hooks` v5, `mypy` v1.13, `isort` 5.13, `black` 24.10, `blacken-docs` 1.19, `flake8` 7.1). Refresh with `pre-commit autoupdate` and re-run `pre-commit run --all-files` before merging.
- **flake8** config: `.flake8`. Line length 100. Ignores E266/E203/E231/W503.

## Branch conventions

- Production deploys ship from `main`.
- Revival work happens on `claude/revive-literature-site-*` branches and is reviewed before merge.
- Modernization work after the initial revival happens on `claude/modernize-*` branches.

## Versioning and releases

After Phase 15 lands, every PR that changes runtime behaviour, dependencies, settings, CI, deploy scripts, or public docs **must** bump `version` in `pyproject.toml` and add a matching `## v<new-version>` section to `RELEASES.md` describing the change. The version field is the trigger for the release pipeline — no bump means no release.

Bump heuristic:

- **PATCH** (`x.y.Z`) — bugfixes, dependency security bumps, infra-only tweaks with no user-visible behaviour change.
- **MINOR** (`x.Y.0`) — additive features, schema additions, new templates, new settings modules, CI parity work.
- **MAJOR** (`X.0.0`) — URL or template structure breaks, removal of public views, anything that could surprise an unsuspecting visitor.

If unsure which level to pick, **ask the human reviewer before merging.** When running as Claude Code, ask via `AskUserQuestion` rather than guessing.

Tagging and the GitHub Release are produced automatically by `.github/workflows/release.yml` once the bumped `pyproject.toml` and the matching `RELEASES.md` section land on `main`. The workflow refuses to run if the `## v<version>` heading is missing — that's the safety net. **Do not** create tags manually.

The first release will be `v1.0.0` once Phase 11 lands and the site goes live. Pre-Phase-11 work flows on the `claude/revive-literature-site-*` branch as a single multi-PR effort; no per-PR version bump is required during the revival.

## After opening a PR

Once a PR is posted, watch it. If `main` advances and the PR develops merge conflicts, resolve them on the PR branch and push the merge commit — don't leave the PR sitting in a conflicted state waiting for the human reviewer to rebase. When the conflict is in `pyproject.toml` / `RELEASES.md` because another PR landed a version bump, renumber your section to the next appropriate level on top of the new `main` version (re-apply the PATCH / MINOR / MAJOR heuristic above against the new base) and update any `docs/SECURITY.md` "Fixed in vX.Y.Z" cross-references to match. Re-run `pytest` and `pre-commit` after the merge before pushing.

## Outstanding work

The GitHub issue tracker is the single source of truth for outstanding work: <https://github.com/kgdunn/Django-app-Literature-database/issues>. The original `todo.txt` from 2010 is preserved verbatim at [`docs/legacy-todo.md`](docs/legacy-todo.md) (with each item mapped to a revival phase); don't duplicate the list here — it goes stale.

The revival roadmap (Phases 0–15) is summarized in the **Revival status** table at the top of this file. Each phase is one PR; the plan file at `/root/.claude/plans/we-have-this-code-validated-brooks.md` has the long-form description.

## Keeping this file consistent

CLAUDE.md must stay consistent with the codebase. On any PR that touches `items/`, `tagging/`, `pagehit/`, `pages/`, `kg/`, `literature/`, `pyproject.toml`, `RELEASES.md`, `Makefile`, `.pre-commit-config.yaml`, or `.github/workflows/`, re-read this file before opening the PR and update anything that has drifted — Revival status, Project shape, How it runs, Gotchas, Tooling, Branch conventions, Versioning and releases. If you're Claude Code, run this consistency check on every implementation task, not just when explicitly asked.
