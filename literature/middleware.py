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

CSP currently allows ``'unsafe-inline'`` for both `script-src` and
`style-src` because `templates/base.html` ships an inline ``<style>``
block (the design tokens + layout) and a couple of small inline
``<script>`` blocks (the early-applied theme preference and the theme
toggle button). Externalising them is queued for a future phase that
moves the CSS / JS into static files; the bleach filter on
`Item.abstract` already keeps the high-risk surface (admin-pasted HTML)
out of the inline-script ambit.

CDN allowlist:
* `cdn.jsdelivr.net` — host of the SRI-pinned MathJax 2.7.9 script
  (Phase 6) used to render LaTeX in `Item.abstract`. The integrity
  hash in `templates/base.html` ensures the bytes can't drift without
  the browser refusing to execute the script.
* `fonts.googleapis.com` + `fonts.gstatic.com` — Google Fonts (IBM Plex
  Sans / Serif / Mono) loaded from base.html.
"""

from django.conf import settings

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
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
