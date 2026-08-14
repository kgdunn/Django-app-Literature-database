# Built-in imports
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone

# Imports from other apps
from .models import PageHit

static_items = {
    # Item-pks here are sentinel negatives — they don't reference a real
    # row in items_item, they just keep PageHit's `item_pk` column distinct
    # per static surface so the admin's date_hierarchy / list_filter still
    # group cleanly. Filtering by `item=` is the canonical way to slice
    # static-page traffic; `item_pk` is just an extra coordinate.
    #
    # The `haystack_search` key is deliberately preserved — despite the
    # Phase-3 replacement of Haystack by Postgres FTS in `pages.search`,
    # this string is what has been written into `PageHit.item` for every
    # search hit since 2010, so renaming it would either fragment the
    # historical series (search-term counts stop working across the
    # rename boundary) or require a data migration. The pre-Phase-3 URL
    # `name="haystack_search"` on the search route is preserved for the
    # same reason (see CLAUDE.md gotcha #13).
    "lit-main-page": -1,
    "haystack_search": -2,
    "lit-about-page": -3,
    "lit-show-all-items": -4,
    "lit-show-all-tags": -5,
    "lit-tag-page": -6,
    "lit-author-page": -7,
    "lit-year-page": -8,
    "lit-journal-page": -9,
}

PROFANITIES_LIST = (
    "asshat",
    "asshead",
    "asshole",
    "cunt",
    "fuck",
    "gook",
    "nigger",
    "shit",
)


def create_hit(request, item, extra_info=None):
    """
    Given a Django ``request`` object, create an entry in the DB for the hit.

    If the ``item`` is a string, then we assume it is a static item and use
    the dictionary above to look up its "primary key".

    Phase 4 trimmed PII storage: ``ua_string`` and ``ip_address`` were
    dropped from the PageHit schema, so the only data captured per hit is
    (item, item_pk, datetime, extra_info). The ``request`` argument is
    kept on the signature so callers don't all have to change at once,
    even though the body no longer reads it.
    """
    del request  # captured for signature stability; PII trim drops use of it
    if extra_info is None:
        extra_info = ""

    if isinstance(item, int):
        page_hit = PageHit(item="item", item_pk=item, extra_info=extra_info)
    elif isinstance(item, str):
        page_hit = PageHit(item=item, item_pk=static_items.get(item, 0), extra_info=extra_info)
    else:
        return  # unknown item type; refuse silently rather than 500

    page_hit.save()


def get_search_hits():
    """
    Returns a list of tuples of the form:  [(n_hits, "search term"), ....]
    sorted in **descending order by n_hits** (most-searched terms first).
    Ties on ``n_hits`` are broken by descending search-term string.

    Search terms are NFKD-normalised, ASCII-folded, lowercased, and stripped
    before counting; terms in ``PROFANITIES_LIST`` are excluded.
    """
    page_hits = PageHit.objects.filter(item_pk=static_items["haystack_search"])
    hits_by_search = defaultdict(int)

    for hit in page_hits:
        term = unicodedata.normalize("NFKD", hit.extra_info or "").encode("ascii", "ignore").decode("ascii")
        term = term.strip().lower()
        if term not in PROFANITIES_LIST:
            hits_by_search[term] += 1

    hit_counts = sorted((value, key) for (key, value) in hits_by_search.items())
    hit_counts.reverse()
    return hit_counts


def get_pagehits(item, start_date=None, end_date=None, item_pk=None):
    """
    Counts page hits in the closed window ``[start_date, end_date]``
    (both endpoints inclusive; defaults span all time).

    With ``item_pk=None`` (default), aggregates hits across every item of
    type ``"item"`` and returns a list of tuples ``[(n_hits, pk), ...]``
    sorted in **descending order by n_hits** (most-viewed items first).

    With ``item_pk`` set, restricts the count to that single ``(item, item_pk)``
    pair and returns the total page-view count as an integer.

    Note: the ``item`` argument is ignored when ``item_pk`` is None - the
    aggregate query is hard-coded to ``item="item"``.
    """
    if start_date is None:
        start_date = datetime(1, 1, 1, tzinfo=timezone.utc)

    if end_date is None:
        end_date = datetime(9999, 12, 31, tzinfo=timezone.utc)

    # Aggregate hits across every "item"-typed PageHit row in the window.
    if item_pk is None:
        page_hits = PageHit.objects.filter(item="item").filter(datetime__gte=start_date).filter(datetime__lte=end_date)
    else:
        page_hits = (
            PageHit.objects.filter(item=item)
            .filter(datetime__gte=start_date)
            .filter(datetime__lte=end_date)
            .filter(item_pk=item_pk)
        )

        return len(page_hits)

    hits_by_pk = defaultdict(int)
    for hit in page_hits:
        hits_by_pk[hit.item_pk] += 1

    hit_counts = sorted((value, key) for (key, value) in hits_by_pk.items())
    hit_counts.reverse()
    return hit_counts
