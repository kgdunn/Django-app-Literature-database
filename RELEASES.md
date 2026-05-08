# Releases

## v1.0.0

First tagged release of the revived `literature.learnche.org`. Captures the multi-PR 2026 modernization of the original 2010-era Django 1.11 / Python 2 codebase that was defunct mid-2010s. The site is now Django 5.2 LTS / Python 3.11 / Postgres / Docker on Hetzner, behind Caddy + Cloudflare, with a privacy-respecting view counter, a Postgres-FTS search backend, and S3 nightly backups.

### Phases landed

The revival was sequenced as 11 phases plus the `master` → `main` rename, each shipping as its own PR:

- **Phase 0** (#1) — repo hygiene baseline. `CLAUDE.md`, `pyproject.toml` (uv), `Makefile`, pre-commit, `.gitignore`, `.editorconfig`, `.flake8`, `.python-version` (3.11), `.dockerignore`, `.env.example`, `docs/legacy-todo.md` archive.
- **Master → main rename** (#2) — default-branch rename with corresponding doc updates.
- **Phase 1** (#3) — Python 2 → 3 + Django 1.11 → 5.2 port. `unicode()` → `str()`, `cStringIO` → `io.BytesIO`, `from django.core.urlresolvers` → `django.urls`, `url()` → `re_path()`, `render_to_response(..., RequestContext)` → `render(...)`, explicit `on_delete=` on every FK, `pdfminer` → `pdfplumber`, `mimetype=` → `content_type=`, `is_authenticated()` → `is_authenticated`. Dropped the `local_settings.py` shim and the haystack imports.
- **Phase 2** (#4) — settings split + `SecurityHeadersMiddleware` + `.env`-driven config. `literature/settings/{base,dev,prod,ci}.py`. `env()` / `env_list()` helpers reading `os.environ` first then `.env`. `SECRET_KEY` mandatory. CSP / Permissions-Policy / Cross-Origin-Opener-Policy on every response. Production-only HSTS, secure cookies, `X-Frame-Options: DENY`, Caddy proxy headers.
- **Phase 3** (#5) — drop Haystack, add Postgres FTS. `pages.search` rewritten with `SearchVector` (title-A / abstract-B / other_search_text-C) + `SearchRank` + `TrigramSimilarity > 0.3` on author last names. `search_type='websearch'` so `-foo` excludes and quoted phrases preserve order. New migration `items/0004_pg_trgm` installs the `pg_trgm` extension. **Dev now runs against Postgres** (not SQLite) so the FTS / trigram code paths are exercised the same way locally and in production.
- **Phase 4 + Phase 5** (#6, combined) — privacy / copyright cleanup.
  - PageHit PII trim: `ua_string` and `ip_address` columns dropped via `pagehit/0003_drop_pagehit_pii`. The schema now holds only `(id, datetime, item, item_pk, extra_info)` — privacy-safe to retain indefinitely. Admin is read-only (append-only audit log).
  - The legacy IP-allowlist gate on `download_item` removed (it was security-theatre behind Cloudflare's edge-IP rewrite).
  - Public PDF download path **removed entirely** (copyright restriction). `items.download_item` and the `lit-download-pdf` URL pattern are gone; `Item.private_pdf` and `Item.can_show_pdf` flags dropped via `items/0005_drop_pdf_visibility_flags`. PDFs remain admin-uploaded archival storage, consumed only by `__extract_extra__` for FTS extraction.
  - New `items/templatetags/extra_tags.py` with `sanitise_markup` template filter — bleach allowlist over `Item.abstract` (`a, b, i, em, strong, sub, sup, code, br, p, span, ul, ol, li, dl, dt, dd`).
- **Phase 6** (#7) — templates modernization. `templates/base.html` rewritten with IBM Plex design tokens (light + dark theme via `prefers-color-scheme` + `data-theme`), tri-state theme toggle persisted in `localStorage`, mobile-first viewport, **SRI-pinned MathJax 2.7.9** from `cdn.jsdelivr.net`. Front page got a 5-portal layout (Recently added / Tag cloud / Most viewed / **Browse by year** / Top search terms). Detail page is a `<dl>` meta layout that grids on ≥600 px and stacks on mobile. Items table reflows into cards under 768 px. CSP shrunk: dropped `cdnjs.cloudflare.com` from the `script-src` allowlist.
- **Phase 7** (#8) — Dockerize. Multi-stage `Dockerfile` (uv builder + `python:3.11-slim` runtime, runs as UID 1000 `app`, gunicorn on `:8000`, `HEALTHCHECK` curls `/healthz`). `docker-compose.yml` for dev with a Postgres sidecar + `runserver` hot-reload. `docker-compose.prod.yml` for prod, loopback-only on offset ports `127.0.0.1:8002` (web) / `127.0.0.1:5435` (db) — coexists with the openmv stack on the same Hetzner host. New `pages.healthz` view (plain-text `ok`, `Cache-Control: no-store`, no DB hit).
- **Phase 8** (#9 + a fixup) — tests + CI workflow + Dependabot. 35 tests in `items/tests/` (14 model + 21 view, including security-header presence and the negative tests pinning the no-public-PDF-download guarantee). `.github/workflows/ci.yml` boots a `postgres:16-alpine` service container (digest-pinned), runs pre-commit + pytest + non-blocking pip-audit. Third-party actions SHA-pinned. `.github/dependabot.yml` for weekly `github-actions` + `docker` ecosystem bumps. The fixup commit added a global `exclude:` for migrations to `.pre-commit-config.yaml` and cleared a long tail of pre-existing flake8 debt that the first CI run surfaced.
- **Phase 9** (#11) — Hetzner deploy automation + bootstrap runbook. `bin/deploy-impl.sh` (host-side: `docker compose up -d --build` + sanity-curl `127.0.0.1:8002/healthz`). `.github/workflows/deploy.yml` SSHes to Hetzner via a forced-command key. `docs/deploy.md` is the full one-time host-bootstrap runbook (Cloudflare DNS, Origin Cert, Caddy server block with `/media/literature/pdf/*` 404 guard, SSH deploy key, GitHub repo secrets).
- **Phase 10** (#39 + #40) — legacy data import. `manage.py import_legacy_dump --file <path>` consumes a Django `dumpdata --all` JSON snapshot from the connectmv.com / Mercurial-era 2010-2018 install. Idempotent (legacy `pk`s preserved via `update_or_create`); handles multi-table inheritance, M2M, `AuthorGroup`, the `media/` prefix on `Item.pdf_file`, and the Phase-4/5 dropped fields. 11 new tests. `docs/data-import.md` is the runbook (later corrected in #40 to use `docker cp …:/tmp/` instead of an unreachable bind-mount path).
- **Phase 11** (#41) — S3 nightly backups. `bin/backup-literature.sh` runs nightly under `deploy` from cron at 22:35 UTC (one hour offset from openmv's 21:35). Three things: `pg_dump` of the `db` container → `db/daily/`, monthly + yearly promotions, retention pruning (15 / 12 / ∞); `aws s3 sync` of `data/media/` (the PDF library — irreplaceable) and `data/public/`; **without `--delete`** so an accidental local rm or detached bind-mount doesn't propagate off-host. Sharing the existing `openmv-backups` bucket via the `literature/` prefix with a separate IAM user. `docs/backup.md` is the full one-time AWS + Hetzner bootstrap runbook with restore drill and disaster-recovery section.

### Phase 15 itself (this release)

- **`RELEASES.md`** — this file. Authoritative release record going forward.
- **`.github/workflows/release.yml`** — auto-tags + creates a GitHub Release whenever the version in `pyproject.toml` changes on `main` and there is a matching `## v<version>` section here. Mirrors openmv's release pipeline (SHA-pinned `actions/checkout`).
- **`.github/workflows/deploy.yml`** — **gated on CI success.** Trigger changed from `push: branches: [main]` to `workflow_run: workflows: ["CI"], types: [completed], branches: [main]` with a job-level `if` filter requiring `github.event.workflow_run.conclusion == 'success'`. A failed CI run no longer deploys. `workflow_dispatch` (manual rollback / forced redeploy) still fires unconditionally.
- **`pyproject.toml`** version bumped `0.1.0` → `1.0.0`.

### Versioning

From here the project follows semver:

- **PATCH** — bugfixes, dependency security bumps, infra-only tweaks with no user-visible behaviour change.
- **MINOR** — additive features, schema additions, new templates, new settings modules, CI parity work.
- **MAJOR** — URL or template structure breaks, removal of public views, anything that could surprise an unsuspecting visitor.

Every PR after this release should bump `pyproject.toml` `version` and add a matching `## v<new-version>` section to this file. The release workflow refuses to run if the heading is missing — that's the safety net.

### How v1.0.0 was tagged

The Phase 15 PR bumped `pyproject.toml` `version` to `1.0.0` and added this section. Once that PR merged to `main`, `.github/workflows/release.yml` auto-detected the version change and published the GitHub Release.
