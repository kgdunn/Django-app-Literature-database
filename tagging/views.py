from collections import defaultdict

from .models import Tag


def get_tag_uses():
    """
    Returns a list of tuples of the form:  [(n_uses, Tag.pk), ....]
    sorted in **descending order by n_uses** (most-used tags first).
    Ties on ``n_uses`` are broken by descending ``Tag.pk``.

    The tuple shape ``(n_uses, Tag.pk)`` is preserved so callers can re-sort
    with the builtin ``list.sort()`` if a different order is needed.
    """
    uses_by_pk = defaultdict(int)
    for tag in Tag.objects.all():
        for item in tag.item_set.all():
            uses_by_pk[tag.pk] += 1

    hit_counts = sorted((value, key) for (key, value) in uses_by_pk.items())
    hit_counts.reverse()

    return hit_counts
