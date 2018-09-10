# BSD-licensed code used here:
# https://github.com/coleifer/djangosnippets.org/blob/master/cab/templatetags/core_tags.py

from django import template
register = template.Library()


from django.apps import apps
from django.db.models.query import QuerySet
from django.db.models.fields import DateTimeField, DateField

from pagehit.views import get_pagehits
from pagehit.views import get_search_hits
from items.models import Item
from tagging.views import get_tag_uses
from tagging.models import Tag

from collections import namedtuple
from math import log


@register.filter(name='most_searched')
def most_searched(field, num=5):
    """ Get the most viewed items from the Submission model """
    top_items = get_search_hits()
    out = []
    for score, search_term in top_items[:num]:
        out.append(search_term)
    return out


@register.filter
def most_viewed(field, num=5):
    """ Get the most viewed items from the Submission model """
    top_items = get_pagehits(field)
    #top_items.sort(reverse=True)
    out = []
    for score, pk in top_items[:num]:
        out.append(Item.objects.get(id=pk))
        out[-1].score = score
    return out


@register.filter
def cloud(model_or_obj, num=5):
    """ Get a tag cloud. If num==0 it will return all the tags."""
    tag_uses = get_tag_uses()
    if not(tag_uses):
        return []
    if num > 0:
        tag_uses = tag_uses[:num]

    max_uses = max(tag_uses[0][0], 5)
    min_uses = tag_uses[-1][0]

    # Use a logarithmic scaling between 1.0 to 170% of baseline font size
    # We could consider a logarithmic scale
    min_font, max_font = 3, 6
    slope = (max_font-min_font)/(max_uses - min_uses + 0.0)
    intercept = min_font - slope * min_uses

    out = []
    Item = namedtuple('Item', 'slug tag score')
    for score, pk in tag_uses:
        tag = Tag.objects.get(id=pk)
        out.append(Item(tag.slug,
                        tag,
                        int(log(slope*score + intercept)*100)-9))

    out.sort()
    return out
