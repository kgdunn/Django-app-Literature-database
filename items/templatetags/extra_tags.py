"""Defence-in-depth template filter for admin-authored markup.

`sanitise_markup` runs an admin-input string through a strict bleach
allowlist before letting Django render it. The CSP middleware
(``literature.middleware.SecurityHeadersMiddleware``) is the first
line of defence; this filter is the second line for the specific
fields the admin can paste arbitrary HTML into (chiefly
``Item.abstract``).

Allowlist is intentionally narrow: the inline tags one might use in an
academic abstract (`<i>`, `<b>`, `<sub>`, `<sup>`, …) plus a couple of
block tags for paragraphs and lists. No `<script>`, no `<iframe>`, no
event handlers, no `javascript:` URLs.

LaTeX written as ``\\(...\\)`` survives because bleach treats
backslashes and parentheses as text; MathJax then renders it
client-side.
"""

import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


ALLOWED_TAGS = frozenset(
    {
        "a",
        "b",
        "i",
        "em",
        "strong",
        "sub",
        "sup",
        "code",
        "br",
        "p",
        "span",
        "ul",
        "ol",
        "li",
        "dl",
        "dt",
        "dd",
    }
)

ALLOWED_ATTRIBUTES: dict[str, list[str]] = {
    "a": ["href", "title"],
    "span": ["class"],
    "code": ["class"],
}

ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto"})


@register.filter(name="sanitise_markup", is_safe=True)
def sanitise_markup(value):
    """Strip every HTML construct outside the allowlist before rendering.

    Returns a ``mark_safe`` string so Django doesn't double-escape the
    bleach-cleaned HTML on the way out. Bleach has already stripped
    anything dangerous, so this is safe.
    """
    if value is None:
        return ""
    cleaned = bleach.clean(
        str(value),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    return mark_safe(cleaned)


@register.simple_tag(name="sparkline_svg")
def sparkline_svg(series, width=160, height=28):
    """Inline SVG sparkline of ``(year, count)`` data points.

    Issue #27. No CDN dependency — a single ``<polyline>`` does the
    rendering. Uses ``currentColor`` for the stroke so the line picks
    up the surrounding text colour and works in light/dark themes
    automatically.

    Returns an empty string for empty / single-point / all-zero
    series so the calling template can use ``{% if %}`` to suppress
    the wrapper element when there's nothing meaningful to plot.
    """
    if not series or len(series) < 2:
        return ""
    counts = [c for _, c in series]
    cmax = max(counts)
    if cmax <= 0:
        return ""
    pad = 2
    plot_w = max(1, width - 2 * pad)
    plot_h = max(1, height - 2 * pad)
    yrs = [y for y, _ in series]
    ymin, ymax = yrs[0], yrs[-1]
    yspan = max(1, ymax - ymin)
    points = []
    for year, count in series:
        x = pad + (year - ymin) * plot_w / yspan
        y = pad + plot_h - (count / cmax) * plot_h
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    svg = (
        f'<svg class="lit-sparkline" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        f'role="img" aria-label="Articles per year, {ymin} to {ymax}, '
        f'peak {cmax}">'
        f'<polyline points="{polyline}" fill="none" stroke="currentColor" '
        f'stroke-width="1.2" stroke-linejoin="round" '
        f'stroke-linecap="round"/>'
        f"</svg>"
    )
    return mark_safe(svg)
