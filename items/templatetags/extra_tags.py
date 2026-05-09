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
