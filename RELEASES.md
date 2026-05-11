# Releases

## v1.1.1

Raise the Python line-length convention from 88 (black's default) to 120 across the toolchain, and reformat the codebase to match. Pure mechanical change; no behavioural, schema, URL, or template impact. Motivated by repeated friction wrapping new test signatures and call sites to fit under 88 — at 120 most one-liners stay readable on modern displays and black stops fighting human-natural call composition.

- **`pyproject.toml`** — new `[tool.black]` and `[tool.isort]` sections, each pinning `line-length = 120` / `line_length = 120`. Black auto-picks this up; isort needs both `--profile black` (other style defaults) **and** an explicit length override (the `black` profile would otherwise clamp it back to 88).
- **`.flake8`** — `max-line-length` raised from 100 to 120 so the lint stage matches the formatters.
- **`.pre-commit-config.yaml`** — isort hook gains `--line-length 120` after `--profile black` (CLI overrides config-file precedence); blacken-docs hook gains `--line-length 120`; black hook unchanged (it reads `[tool.black]` from `pyproject.toml`). Each change has a short rationale comment so a future maintainer doesn't "tidy" them away.
- **`CLAUDE.md`** — Tooling section's flake8 bullet rewritten to call out the unified line-length policy across black + isort + blacken-docs + flake8, with the gotcha about the isort-profile-black clamp made explicit.
- **Codebase reformat** — `black --line-length 120` and `isort --profile black --line-length 120` run across the repo (excluding `(items|tagging|pagehit)/migrations/` as the pre-commit `exclude:` already does). 19 source files reflowed; net diff -294 / +98 lines, almost entirely existing multi-line signatures and call sites collapsing to single lines under the new limit. Black's "magic trailing comma" rule kept any block that already had a trailing comma multi-line, so the per-arg-per-line shape stays everywhere it existed.
- **`pyproject.toml`** / **`RELEASES.md`**: PATCH bump (infra-only tooling tweak + cosmetic reformat; no user-visible behaviour change), per the policy in `CLAUDE.md`.

The companion change in the openmv stack (`kgdunn/Django-dataset-download-app`) is intentionally **not** part of this PR — the operator opted to keep the scope to literature for now. If we want to mirror the convention there later, it's a one-shot follow-up of the same shape.

## v1.1.0

Show article abstracts on the detail page by default. Previously, every
detail page suppressed the abstract behind ``Item.show_abstract``, which
defaulted to ``False`` and was never flipped to ``True`` for the
imported legacy corpus. Abstracts existed in the DB (FTS already
indexed them — they were searchable but invisible on the actual item
page) and never reached the reader. The 2010-era design intended
``show_abstract`` as an admin opt-in gate, but the revived site has no
review workflow that would flip it, so it had become a permanent "off"
switch for every abstract on the site. Drop the field entirely; gate
on ``Item.abstract`` content in the template instead.

- **`items/templates/items/item.html`** — the abstract block now gates
  on ``{% if item.abstract %}`` instead of ``{% if item.show_abstract %}``.
  Rendering pipeline (bleach allowlist + MathJax for ``\(...\)``)
  unchanged.
- **`items/models.py`** — ``Item.show_abstract`` field declaration
  removed. If a specific abstract ever needs hiding, clear the
  ``abstract`` field instead.
- **`items/migrations/0010_remove_item_show_abstract.py`** — new
  migration drops the column. Standard
  ``ALTER TABLE items_item DROP COLUMN show_abstract``; reversible via
  the operation's auto-generated inverse.
- **`items/admin.py`** — no changes needed; ``show_abstract`` was
  never on ``ItemAdmin.list_display`` or ``fields``.
- **`items/tests/conftest.py`** — ``journalpub_factory`` no longer
  passes ``show_abstract=True`` (the kwarg would now raise
  ``TypeError: got an unexpected keyword argument`` since the field
  is gone).
- **`items/tests/test_views.py`** — two ad-hoc ``objects.create``
  calls (in ``test_journal_name_in_search_vector`` and
  ``test_conference_name_in_search_vector``) drop the
  ``show_abstract`` kwarg. Two new ``TestItemDetail`` tests pin the
  new behaviour:
  ``test_abstract_renders_when_non_empty`` (abstract content surfaces
  under a ``<dt>Abstract</dt>`` block) and
  ``test_abstract_section_omitted_when_empty`` (empty abstract
  produces no Abstract header, no empty ``<dd>``).
- **`items/tests/test_import_legacy_dump.py`** — fixture and test
  comments updated: ``"show_abstract": True`` in legacy JSON now joins
  the silently-dropped-field set, alongside the Phase-5
  ``private_pdf`` / ``can_show_pdf`` and Phase-4 ``ua_string`` /
  ``ip_address`` fields. The existing
  ``test_dropped_fields_are_silently_ignored`` covers the path.
- **`CLAUDE.md`** — Project shape / Models entry no longer lists
  ``show_abstract`` among ``Item`` fields; Templates / Gotchas
  updated to describe the new ``{% if item.abstract %}`` gate; a
  pointer in Gotcha 5 tells the future maintainer to clear the
  ``abstract`` field rather than reintroduce a ``show_abstract``-style
  boolean.
- **`pyproject.toml`** / **`RELEASES.md`** — MINOR bump per the
  policy in ``CLAUDE.md`` (additive visible behaviour change on a
  public page: abstract content that was suppressed now appears for
  every item that has it; no URL change, no template-structure break).

**Visitor impact**: every article-detail page now surfaces the
abstract inline below the citation block, wrapped in the same bleach
allowlist + MathJax rendering pipeline used elsewhere. Items without
an abstract (``blank=True``) render as before — no extra heading.

## v1.0.3

Bugfix + runbook for the 2026-05-10 live-site incident. Two unrelated failures stacked: Caddy on the shared Hetzner host had a JSON config hot-pushed to its admin API on `localhost:2019` that 403'd every request with `Host not in allowlist` (custom `x-deny-reason: host_not_allowed` header), and once that was unblocked, every DB-touching page 500'd because `pagehit_pagehit.id`'s Postgres sequence was still at 1 — a latent bomb left by Phase 10's `import_legacy_dump`, which writes rows with explicit legacy pks but never bumped the sequences afterwards. `pages.healthz` was the only view that didn't trigger the integrity error, which masked the second failure for over an hour.

- **`items/management/commands/import_legacy_dump.py`** — append a `_reset_sequences` step at the end of every non-dry-run import. Captures `manage.py sqlsequencereset items pagehit tagging` into a `StringIO`, then executes the resulting `setval(...)` statements against the live connection in one cursor call. Idempotent: running it on an empty result set is a no-op. The import command stays inside its own `transaction.atomic()` for the row inserts; the sequence reset runs after the commit so a rolled-back dry run leaves sequences untouched. Closes the live-site bomb for any future imports against this command.
- **`docs/deploy.md`** — new `## Troubleshooting` section with the two failure-mode runbooks: the Caddy admin-API override (symptom + `admin off` + restart fix) and the stale `pagehit` sequence (symptom + `sqlsequencereset … | dbshell` one-shot). Future-you reads these and recovers in one shot instead of an hour of grep.
- **`pyproject.toml`** / **`RELEASES.md`** — PATCH bump per `CLAUDE.md`'s policy (a behavioural bugfix in the import command + a doc addition; no template, URL, dependency, or schema change).

The Caddy `admin off` change is server-side only — applied on the Hetzner host as part of the incident response, not version-controlled in this repo (the Caddyfile lives in `/etc/caddy/` outside any git tree). The runbook in `docs/deploy.md` is the durable record of what was done.

## v1.0.2

Documentation: rename the off-host backup S3 bucket from `openmv-backups`
to `kgd-backups` in docs and the `bin/backup-literature.sh` header
comment, reflecting the actual shared-bucket name used in production.
The bucket itself was renamed when the live backup setup was wired up on
the Hetzner host on 2026-05-10; this PR brings the docs in sync. The
script reads the bucket name from `$BACKUP_S3_BUCKET` in `.env`, so no
runtime / CI / template / dependency change.

- **`docs/backup.md`** — every reference to `openmv-backups` (intro
  paragraph, S3 layout block, IAM policy ARNs in 1b, `.env` example
  block, verify / restore commands, real-disaster-recovery commands,
  troubleshooting) updated to `kgd-backups`.
- **`CLAUDE.md`** — Backups-section parenthetical now reads
  ``(`kgd-backups`)`` instead of ``(`openmv-backups`)``.
- **`bin/backup-literature.sh`** — header comment example for
  `BACKUP_S3_BUCKET` updated. Runtime behaviour unchanged; the script
  reads the bucket name from `.env`.
- **`pyproject.toml`** / **`RELEASES.md`**: PATCH bump (docs +
  comment, no user-visible behaviour change), per the policy in
  `CLAUDE.md`.
- The matching docs rename in the openmv stack
  (`kgdunn/Django-dataset-download-app`) is shipped in a sibling PR
  on the same branch name.

## v1.0.1

Supply-chain modernization: migrate the Postgres driver from
`psycopg2-binary` (legacy, feature-frozen as of 2024) to `psycopg[binary]`
(psycopg3, actively maintained, native-async, type-aware). Issue #85;
mirrors openmv's audit finding #13. Also a pre-req for Phase 12 pgvector
which prefers psycopg3.

- `pyproject.toml` — `psycopg2-binary>=2.9.12` →
  `psycopg[binary]>=3.1,<4`. Re-locked via `uv lock`.
- `Dockerfile` runtime stage — `libpq5` removed from the apt install
  list. `psycopg[binary]` ships a self-contained binary wheel that
  bundles its own libpq, so the system package is no longer needed.
  Trims a couple of MB from the runtime image.

Django 5.2 supports both psycopg2 and psycopg3 transparently; no
`DATABASES` config change needed. Django wraps driver exception
classes in `django.db.utils.*`, so application code is unaffected.

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
