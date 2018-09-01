# BSD-licensed code used here:
# https://github.com/coleifer/djangosnippets.org/blob/master/cab/templatetags/core_tags.py

from django import template
register = template.Library()


from django.apps import apps
from django.db.models.query import QuerySet
from django.db.models.fields import DateTimeField, DateField

from items.models import Item
from tagging.models import Tag

from collections import namedtuple
from math import log


@register.filter(name='most_searched')
def most_searched(field, num=5):
    """ Get the most viewed items from the Submission model """
    assert(False) # how can we avoid this import; or place it outside the filter?
    from pagehit.views import get_search_hits
    top_items = get_search_hits()
    top_items.sort(reverse=True)
    out = []
    for score, search_term in top_items[:num]:
        out.append(search_term)
    return out


@register.filter
def most_viewed(field, num=5):
    """ Get the most viewed items from the Submission model """

    assert(False) # how can we avoid this import; or place it outside the filter?
    from pagehit.views import get_pagehits
    top_items = get_pagehits(field)
    top_items.sort(reverse=True)
    out = []
    for score, pk in top_items[:num]:
        out.append(Item.objects.get(id=pk))
        out[-1].score = score
    return out


@register.filter
def cloud(model_or_obj, num=5):
    """ Get a tag cloud """

    from tagging.views import get_tag_uses

    tag_uses = get_tag_uses()
    if not(tag_uses):
        return []
    tag_uses.sort(reverse=True)
    if num != 0:
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
        out.append(Item(tag.slug, tag, int(log(slope*score + intercept)*100)-9))

    out.sort()
    return out

@register.filter
def latest(model_or_obj, num=5):
    # load up the model if we were given a string
    if isinstance(model_or_obj, basestring):
        model_or_obj = apps.get_model(*model_or_obj.split('.'))

    # figure out the manager to query
    if isinstance(model_or_obj, QuerySet):
        manager = model_or_obj
        model_or_obj = model_or_obj.model
    else:
        manager = model_or_obj._default_manager

    # get a field to order by, defaulting to the primary key
    field_name = model_or_obj._meta.pk.name
    for field in model_or_obj._meta.fields:
        if isinstance(field, (DateTimeField, DateField)):
            field_name = field.name
            break
    items = manager.all().order_by('-%s' % field_name)
    return [item for item in items][:num]
