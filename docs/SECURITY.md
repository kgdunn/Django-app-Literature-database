# Security

Canonical security record for the literature.learnche.org Django site.
Captures what's been audited, what's been fixed, what's deferred, so
future maintainers don't have to spelunk PR descriptions to know what
state the site is in.

## Reporting a vulnerability

Please email Kevin Dunn — the maintainer's address is on
<https://learnche.org>. Do **not** open a public GitHub issue for
suspected vulnerabilities; we'll create one once we've assessed the
report and have a fix in flight.

GitHub's "Security" tab on the repo points reporters here via a
top-level [`SECURITY.md`](../SECURITY.md) redirect.

---

## Audit findings (2026-05-09)

A full code review of the application, settings, deployment, and
supply-chain surface, mirroring the audit that landed openmv.net's
[`docs/SECURITY.md`](https://github.com/kgdunn/Django-dataset-download-app/blob/master/docs/SECURITY.md).
Severity reflects the realistic worst case for *this* site (small
read-only public catalogue with one admin behind Cloudflare → Caddy →
Django on Hetzner), not a generic CVSS score.

`pip-audit` was clean at audit time (no known dep CVEs).

| #  | Severity | File / area                               | Issue                                                                                                                                                                                                                                                       | Status                                                                                                                                                                                                                                                                                                                                |
| -- | -------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1  | High     | `Dockerfile:12,29`                        | `FROM python:3.14-slim` was a floating tag — a Docker Hub repoint of `python:3.14-slim` could land silently on the next deploy.                                                                                                                              | **Fixed in this PR.** Both stages pinned to `python:3.14-slim@sha256:5b3879…`. Same digest as openmv so the two stacks share image bytes. Closes #70.                                                                                                                                                                                  |
| 2  | High     | `literature/settings/prod.py:26`          | `SECURE_HSTS_SECONDS = 300` (5 minutes) was a deliberate staged rollout while the Caddy proxy was being verified — but had been sitting at 5 min for weeks past the verification window.                                                                  | **Fixed in this PR (week 1).** Bumped to `31536000` (1 year). `SECURE_HSTS_PRELOAD` stays `False` until a follow-up week confirms no SSL-redirect / mixed-content regressions; only then does the domain get submitted to <https://hstspreload.org/>. Issue #71.                                                                          |
| 3  | High     | `/admin/login/` open to internet          | No per-account lockout on Django admin login. Bruteforce / credential stuffing could iterate forever.                                                                                                                                                       | **Fixed in this PR.** `django-axes` integrated: locks per `(username, ip_address)` tuple after 5 failures for 30 minutes; resets on success. Closes #74. Sub-issue of the /admin/-hardening epic (#73). Other layers (Caddy rate-limit #75, Cloudflare WAF #76, optional IP allowlist #77) are host-side / dashboard tasks, tracked separately. |
| 4  | High     | Admin login is single-factor              | Admin compromise is the highest-impact credential incident for the site (visitor-XSS via injected markup, data tampering). 2FA mitigates.                                                                                                                  | **Open — #78.** `django-otp` + `django-two-factor-auth` integration deliberately deferred to its own PR — it's a maintainer behaviour change (mandatory TOTP enrolment) that needs a coordinated rollout window.                                                                                                                       |
| 5  | Medium   | No `robots.txt`                           | `/admin/` was indexable by search engines. `test.literature.learnche.org` had no `noindex`.                                                                                                                                                                | **Open — #72.** `data/public/robots.txt` with `Disallow: /admin/`; staging gets an `X-Robots-Tag: noindex` header in the Caddy server block.                                                                                                                                                                                          |
| 6  | Medium   | `literature/middleware.py` CSP            | `script-src` allows `https://cdn.jsdelivr.net` for MathJax + ECharts. SRI hashes are pinned, but a tightened CSP would drop the CDN allowance entirely.                                                                                                    | **Open — #79.** Vendor both libraries under `staticfiles/vendor/`, drop the jsdelivr allowance, keep SRI as layered defence.                                                                                                                                                                                                          |
| 7  | Medium   | `literature/middleware.py` CSP            | `'unsafe-inline'` on `script-src` and `style-src` (driven by inline `<style>` block in `templates/base.html` and inline JS for theme toggle / sparkline init).                                                                                              | **Open — #80.** Move inline blocks into static files, tighten CSP to drop `'unsafe-inline'`.                                                                                                                                                                                                                                          |
| 8  | Low      | `Dockerfile:38`                           | Runtime apt installs `libpq5` for `psycopg2-binary`. Switching to psycopg3 would drop the apt-install line entirely.                                                                                                                                       | **Open — #85, deferred.** Pre-req for Phase 12 (pgvector, #64) — landing before that point is wasted churn.                                                                                                                                                                                                                            |
| 9  | Low      | `items/models.py` `Item.pdf_file`         | No `FileExtensionValidator` — admin form accepts any file extension. PDFs aren't publicly served (Phase 5), so the XSS-via-uploaded-HTML risk that openmv finding #5 closed isn't applicable; this is data-quality only.                                  | **Open — #82.** Add `FileExtensionValidator(allowed_extensions=["pdf"])` to the field.                                                                                                                                                                                                                                                |
| 10 | Low      | `tagging/models.py` `Tag.save()`          | Silent no-op on slug collision: a duplicate `Tag.objects.create(...)` returns "saved" without persisting. Also blocks legitimate description updates because the row treats itself as a collision.                                                       | **Open — #83.** Use `IntegrityError` on real collision; skip the check when `self.pk is not None` (update path).                                                                                                                                                                                                                       |
| 11 | Low      | `pagehit/admin.py:18`                     | `list_per_page = 200` — out of step with `items/admin.py`'s 100 and openmv's audit anchor.                                                                                                                                                                | **Open — #84.** Lower to 100 for consistency.                                                                                                                                                                                                                                                                                          |
| 12 | Low      | `.github/dependabot.yml`                  | Covers `github-actions` + `docker` only. Python deps in `pyproject.toml` only refresh on manual `uv lock --upgrade`.                                                                                                                                       | **Open — #81.** Add `pip` (or `uv`) ecosystem on a weekly schedule.                                                                                                                                                                                                                                                                   |

### Already-correct findings (no change needed)

- ORM-only DB access — no `.raw()` / `.extra()` / cursor strings; SQL injection surface is zero.
- All public views are GET-only — no CSRF surface today (Phase 5 removed the only POST surface, the IP-gated PDF download).
- `SECRET_KEY` is asserted in `literature/settings/base.py` — fails loudly if missing.
- `CSRF_TRUSTED_ORIGINS` correctly scoped to `https://literature.learnche.org` + `https://test.literature.learnche.org`; no wildcards.
- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` correctly trusts only the Caddy-stripped header.
- `docker-compose.prod.yml` binds both `web` and `db` services to `127.0.0.1` only; Caddy is the sole public process.
- `DEBUG = False` in prod (and CI); SQLite is dev-only.
- Cookie + transport flags (`SESSION_COOKIE_HTTPONLY/SECURE/SAMESITE`, `CSRF_COOKIE_HTTPONLY/SECURE/SAMESITE`, `SECURE_REFERRER_POLICY = "same-origin"`, `SECURE_CONTENT_TYPE_NOSNIFF = True`, `X_FRAME_OPTIONS = "DENY"`) all set in `prod.py`.
- Upload limits (`DATA_UPLOAD_MAX_MEMORY_SIZE = 50 MiB`, `FILE_UPLOAD_MAX_MEMORY_SIZE = 50 MiB`, `FILE_UPLOAD_PERMISSIONS = 0o644`) capped in `base.py`.
- `Dockerfile` runtime stage runs as non-root user `app` (UID 1000); `HEALTHCHECK` wired to `/healthz`.
- Dockerfile builder pulls `uv` from a digest-pinned `ghcr.io/astral-sh/uv:0.8.17`.
- The deploy SSH key is restricted to a forced-command wrapper; a leaked key can only re-trigger the deploy script.
- `.dockerignore` excludes `.env`, `.git`, `__pycache__`, etc.
- Phase 5 PDF restriction holds: PDFs are admin-only storage; Caddy `@pdfs path /media/literature/pdf/* / respond 404` block is in `docs/deploy.md`'s reference Caddyfile.
- Bleach sanitisation of `Item.abstract` is in place via the `sanitise_markup` filter (allowlist: `a, b, i, em, strong, sub, sup, code, br, p, span, ul, ol, li, dl, dt, dd`).
- App-built HTML in `Item.full_citation` / `Item.full_author_listing` / `Item.author_list_all_lastnames` is safe by construction (string concatenation of trusted model fields under admin control).
- Search-query construction uses `SearchQuery(..., search_type="websearch")` which dispatches to Postgres' native `websearch_to_tsquery`; user input is parameterised, no raw-SQL surface.
- CI workflow has `permissions: contents: read`, `pip-audit` runs non-blocking, third-party actions pinned by full commit SHA.
- All runtime dependencies have lower bounds in `pyproject.toml`; `pip-audit` is in the dev group.

---

## Host-side recommendations (not enforceable from this repo)

These don't ship in the repo but should be applied on the Hetzner host
or in the Cloudflare dashboard. Each has a follow-up issue.

### Caddy: rate-limit `/admin/login/` — Issue #75

The host-installed Caddy needs the `caddy-ratelimit` module
(<https://github.com/mholt/caddy-ratelimit>). Add to
`/etc/caddy/Caddyfile` in the literature.learnche.org server block:

```caddy
@admin path /admin/*
rate_limit @admin {
    zone admin_login {
        key {http.request.remote.host}
        events 5
        window 1m
    }
}
```

After editing: `sudo caddy validate && sudo systemctl reload caddy`.

### Cloudflare: WAF Managed Challenge on `/admin/*` — Issue #76

In the Cloudflare dashboard for the `learnche.org` zone:

1. **Security → WAF → Custom rules → Create rule**:
   - **When:** `(starts_with(http.request.uri.path, "/admin/")) and (http.host eq "literature.learnche.org")`
   - **Action:** `Managed Challenge`
2. **Caching → Page Rules → Create**:
   - **URL pattern:** `*literature.learnche.org/admin/*`
   - **Setting:** `Cache Level: Bypass`

`test.literature.learnche.org` is **DNS-only** (grey cloud) so these
edge rules don't apply there — Caddy is the only filter for staging,
which is the intended posture.

### fail2ban jail (alternative to caddy-ratelimit) — Issue #75

`/etc/fail2ban/filter.d/caddy-admin.conf`:

```
[Definition]
failregex = ^.*"GET /admin/login/.*" 4[0-9][0-9].*"<HOST>".*$
            ^.*"POST /admin/login/.*" 4[0-9][0-9].*"<HOST>".*$
```

`/etc/fail2ban/jail.d/caddy-admin.conf`:

```
[caddy-admin]
enabled  = true
port     = http,https
logpath  = /var/log/caddy/access.log
maxretry = 5
findtime = 600
bantime  = 3600
```

### HSTS preload — Issue #71

Once a week of production traffic confirms `X-Forwarded-Proto: https`
is being honoured (no SSL-redirect loops, no mixed-content reports),
flip `SECURE_HSTS_PRELOAD = True` in `prod.py` in a separate PATCH
release. Then submit `literature.learnche.org` to <https://hstspreload.org/>.

---

## Issues to file

The full audit produced 17 follow-up issues, tracked under the
security umbrella **#86**. The list:

- **#69** — `docs/SECURITY.md` (this file) + top-level redirect.
  Fixed by this PR.
- **#70** — Pin Dockerfile python base by digest. Fixed by this PR.
- **#71** — HSTS preload rollout (week-1 step). Fixed by this PR;
  follow-up flip of `PRELOAD = True` is a separate small PR.
- **#72** — `robots.txt` + staging `noindex`.
- **#73** — `/admin/`-hardening epic (parent of #74–#77).
- **#74** — `django-axes` for per-account admin login throttling.
  Fixed by this PR.
- **#75** — Caddy `caddy-ratelimit` / fail2ban for `/admin/login/`.
- **#76** — Cloudflare WAF Managed Challenge on `/admin/*`.
- **#77** — `/admin/` IP allowlist (optional, defer).
- **#78** — Enforce 2FA on admin (`django-otp` + `django-two-factor-auth`).
- **#79** — Vendor MathJax + ECharts; drop CDN from CSP.
- **#80** — Eliminate inline `<script>`/`<style>`; drop CSP `'unsafe-inline'`.
- **#81** — Dependabot `pip` (or `uv`) ecosystem for weekly Python dep bumps.
- **#82** — `FileExtensionValidator` on `Item.pdf_file`.
- **#83** — Fix `Tag.save()` silent-no-op on slug collision.
- **#84** — `PageHitAdmin.list_per_page` 200 → 100.
- **#85** — Migrate `psycopg2-binary` → psycopg3 (deferred; pre-req for Phase 12).

---

## Where to look in the code

| Concern                          | File                                                         |
| -------------------------------- | ------------------------------------------------------------ |
| HTML sanitisation (bleach)       | `items/templatetags/extra_tags.py`                           |
| DOI validator + normaliser       | `items/models.py` (`validate_doi_or_url`, `Item._normalize_doi_link`) |
| Admin write-once policy          | `pagehit/admin.py` (`PageHitAdmin.readonly_fields`)          |
| Security headers (CSP / Permissions-Policy / COOP) | `literature/middleware.py`                                  |
| Cookie + transport flags         | `literature/settings/prod.py`                                |
| Upload size limits               | `literature/settings/base.py`                                |
| Admin-login throttling           | `literature/settings/base.py` (`AXES_*`)                     |
| Search-query parameterisation    | `pages/views.py` (`SearchQuery`, `search_type="websearch"`)  |
| PDF download disabled (Phase 5)  | `items/views.py` (no `download_item` view); Caddy `@pdfs respond 404` in `docs/deploy.md` |
| Forced-command deploy SSH        | `bin/deploy-impl.sh`, `.github/workflows/deploy.yml`         |
| Test coverage for security paths | `items/tests/test_views.py` (CSP / TestSecurityHeaders / no-PDF-download class), `items/tests/test_admin_lockout.py` |
