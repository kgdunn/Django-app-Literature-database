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

CSP currently allows ``'unsafe-inline'`` for both `script-src` and
`style-src` because base.html ships an inline ``<style>`` block and a few
templates inline small ``<script>`` snippets. Externalising those is
tracked for Phase 6 (templates modernization).

CDN allowlist:
* `cdn.jsdelivr.net` — target host once Phase 6 switches to jsdelivr-served
  MathJax + ECharts (matching openmv).
* `cdnjs.cloudflare.com` — current host of the legacy MathJax 2.7.5 script
  in templates/base.html. Both entries stay until Phase 6 lands so no
  inline-script regressions appear during the transition.
* `fonts.googleapis.com` + `fonts.gstatic.com` — Google Fonts (Inconsolata,
  Lato) loaded from base.html.
"""

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
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
        return response
