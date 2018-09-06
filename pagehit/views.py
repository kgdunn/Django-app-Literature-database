# Built-in imports
import unicodedata
from datetime import date
from collections import defaultdict

# Imports from other apps
from utils import get_IP_address
from .models import PageHit

from django.conf import settings

static_items = {'lit-main-page': -1,
                'haystack_search': -2,
               }

PROFANITIES_LIST = ('asshat', 'asshead', 'asshole', 'cunt', 'fuck',
                    'gook', 'nigger', 'shit')

def create_hit(request, item, extra_info=None):
    """
    Given a Django ``request`` object, create an entry in the DB for the hit.

    If the ``item`` is a string, then we assume it is a static item and use
    the dictionary above to look up its "primary key".
    """
    ip_address = get_IP_address(request)
    ua_string = request.META.get('HTTP_USER_AGENT', '')
    if extra_info is None:
        extra_info = request.META.get('HTTP_REFERER', None)
    if isinstance(item, int):
        page_hit = PageHit(ip_address=ip_address, ua_string=ua_string,
                           item='item', item_pk=item,
                           extra_info=extra_info)
    elif isinstance(item, str):
        page_hit = PageHit(ip_address=ip_address, ua_string=ua_string,
                           item=item, item_pk=static_items.get(item, 0),
                           extra_info=extra_info)

    page_hit.save()


def get_search_hits():
    """
    Returns a list of tuples of the form:  [(n_hits, "search term"), ....]
    This allows one to use the builtin ``list.sort()`` function where Python
    orders the list based on the first entry in the tuple.
    """
    page_hits = PageHit.objects.filter(item_pk=-2)
    hits_by_search = defaultdict(int)

    for hit in page_hits:
        term = unicodedata.normalize('NFKD', hit.extra_info).encode(\
                                                              'ascii', 'ignore')
        term = term.strip().lower()
        if term not in PROFANITIES_LIST:
            hits_by_search[term] += 1

    hit_counts = []
    for key, val in hits_by_search.iteritems():
        hit_counts.append((val, key))

    return hit_counts

def get_pagehits(item, start_date=None, end_date=None, item_pk=None):
    """
    Returns a list of tuples of the form:  [(n_hits, pk), ....]
    This allows one to use the builtin ``list.sort()`` function where Python
    orders the list based on the first entry in the tuple.

    The list will be returned in the order of the ``pk``, but the
    first tuple entry is the number of hits, allowing for easy sorting
    using Python's ``sort`` method.

    However, if ``item_pk`` is provided, then it simply returns the total
    number of page views for that item, as an integer.
    """
    if start_date is None:
        start_date = date.min
    if end_date is None:
        end_date = date.max

    # extra_info=None to avoid counting download hits
    if item_pk is None:
        page_hits = PageHit.objects.filter(item='item').\
                                       filter(datetime__gte=start_date).\
                                       filter(datetime__lte=end_date)
    else:
        page_hits = PageHit.objects.filter(item=item).\
                                       filter(datetime__gte=start_date).\
                                       filter(datetime__lte=end_date).\
                                       filter(item_pk=item_pk)

        return len(page_hits)

    hits_by_pk = defaultdict(int)
    for hit in page_hits:
        hits_by_pk[hit.item_pk] += 1

    hit_counts = []
    for key, val in hits_by_pk.iteritems():
        hit_counts.append((val, key))

    return hit_counts
