"""Project-local middleware.

`SecurityHeadersMiddleware` adds the browser-side defence-in-depth headers
that Django's `SecurityMiddleware` does not set:

* ``Content-Security-Policy`` — neutralises injected `<script>` (the
  `bleach`-based ``sanitise_markup`` filter — Phase 5 — is the primary
  defence; the CSP is the second line for any future template that
  forgets it).
* ``Permissions-Policy`` — opt out of legacy interest-cohort and the
  device-sensor APIs we don't need.
* ``Cross-Origin-Opener-Policy`` — isolate browsing-context groups.
* ``X-Robots-Tag`` — emitted only when the ``LITERATURE_NOINDEX``
  setting is truthy (issue #72). Staging deploys flip this in their
  ``.env`` so search engines don't index the rehearsal hostname.
  Production deploys leave it off; the per-path ``Disallow`` rules
  in ``/robots.txt`` (also issue #72) keep ``/admin/`` etc. out of
  search results without blanket-blocking the public catalogue.

CSP no longer allows ``'unsafe-inline'`` on either ``script-src`` or
``style-src`` (issue #80, PR landing this comment). The previous
inline blocks — the theme-preload + theme-toggle ``<script>``s and
the giant ``<style>`` in ``templates/base.html``, plus the ECharts
init in ``items/templates/items/show-entries.html`` — were extracted
to ``literature/static/literature/{theme-preload,theme-toggle,sparkline}.js``
and ``…/site.css``. ``style-src`` keeps ``'unsafe-inline'`` only for
the Google Fonts ``<link rel="stylesheet">`` workaround… actually no,
Google Fonts CSS comes from a remote stylesheet, no inline needed.
``style-src`` now is ``'self' https://fonts.googleapis.com``.

CDN allowlist:
* (none for scripts) — issue #79 vendored MathJax + ECharts under
  ``/static`` so ``script-src`` is now a bare ``'self'`` with no
  ``cdn.jsdelivr.net`` allowance. MathJax is the v3 SVG bundle
  (``tex-mml-svg.js``), self-contained with embedded glyph paths, so it
  fetches no web fonts at runtime either. See
  ``literature/static/literature/vendor/README.md`` for provenance.
* ``fonts.googleapis.com`` + ``fonts.gstatic.com`` — Google Fonts
  (IBM Plex Sans / Serif / Mono) loaded from ``base.html``. These are the
  only remaining off-origin allowances (``style-src`` / ``font-src``).
"""

from django.conf import settings

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

PERMISSIONS_POLICY = "interest-cohort=(), camera=(), microphone=(), geolocation=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # Issue #72: full-site noindex on staging. Set LITERATURE_NOINDEX=true
        # in the staging .env; prod leaves the setting unset / false.
        if getattr(settings, "LITERATURE_NOINDEX", False):
            response.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response
