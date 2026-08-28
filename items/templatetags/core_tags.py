# BSD-licensed code used here:
# https://github.com/coleifer/djangosnippets.org/blob/master/cab/templatetags/core_tags.py

from collections import namedtuple
from math import log

from django import template

from items.models import Item
from pagehit.views import get_pagehits, get_search_hits
from tagging.models import Tag
from tagging.views import get_tag_uses

register = template.Library()


@register.filter(name="most_searched")
def most_searched(field, num=5):
    """Return the top ``num`` most-searched query strings.

    Reads the aggregate produced by ``pagehit.views.get_search_hits``
    (already sorted by descending hit count with profanities filtered
    out) and returns just the search-term strings — the hit counts are
    dropped. ``field`` is unused; it exists so the filter can be applied
    in a template as ``{{ ""|most_searched:5 }}``.
    """
    top_items = get_search_hits()
    out = []
    for score, search_term in top_items[:num]:
        out.append(search_term)
    return out


@register.filter
def most_viewed(field, num=5):
    """Return the top ``num`` most-viewed ``Item`` instances.

    Reads the aggregate produced by ``pagehit.views.get_pagehits``
    (descending by hit count) and rehydrates each entry into an
    ``Item`` with the raw hit count attached as ``item.score`` so
    templates can render it alongside the entry. ``field`` is passed
    straight through to ``get_pagehits`` as its ``item`` argument
    (which is ignored in the aggregate branch).
    """
    top_items = get_pagehits(field)
    # top_items.sort(reverse=True)
    out = []
    for score, pk in top_items[:num]:
        out.append(Item.objects.get(id=pk))
        out[-1].score = score
    return out


@register.filter
def cloud(model_or_obj, num=5):
    """Get a tag cloud. If num==0 it will return all the tags.

    Returns a list of namedtuples ``(slug, tag, score, count)``:
        - ``score`` is the rendered font-size percentage for the cloud
          entry (logarithmic scaling, tightened in 2026-05 to a
          smaller range — see issue #34).
        - ``count`` is the raw number of items using the tag, surfaced
          so templates can render it as a superscript next to the tag
          name (issue #38).
    """
    tag_uses = get_tag_uses()
    if not (tag_uses):
        return []
    if num > 0:
        tag_uses = tag_uses[:num]

    max_uses = max(tag_uses[0][0], 5)
    min_uses = tag_uses[-1][0]

    # Logarithmic scaling. Issue #34 asked for a smaller cloud overall;
    # tightening max_font from 6 → 5 narrows the rendered font-size
    # range from ~100–170% to ~100–151% (int(log(5) * 100) - 9 = 151),
    # so the most-used tags don't dwarf the rest.
    min_font, max_font = 3, 5
    slope = (max_font - min_font) / (max_uses - min_uses + 0.0)
    intercept = min_font - slope * min_uses

    out = []
    Item = namedtuple("Item", "slug tag score count")
    for score, pk in tag_uses:
        tag = Tag.objects.get(id=pk)
        out.append(
            Item(
                tag.slug,
                tag,
                int(log(slope * score + intercept) * 100) - 9,
                score,
            )
        )

    out.sort()
    return out
