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
    """Return the top ``num`` most-searched query terms (strings), most-hit first."""
    top_items = get_search_hits()
    out = []
    for score, search_term in top_items[:num]:
        out.append(search_term)
    return out


@register.filter
def most_viewed(field, num=5):
    """Get the most viewed items from the Submission model"""
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
    # range from ~100–170% to ~100–148%, so the most-used tags don't
    # dwarf the rest.
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
