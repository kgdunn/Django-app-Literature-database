from .models import Tag
from collections import defaultdict

def get_tag_uses():
    """
    Returns a list of tuples of the form:  [(n_uses, Tag.pk), ....]
    This allows one to use the builtin ``list.sort()`` function where Python
    orders the list based on the first entry in the tuple.

    The list will be returned in the order of the ``Tag.pk``, but the
    first tuple entry is the number of uses of that tag, allowing for easy
    sorting using Python's ``sort`` method.
    """
    uses_by_pk = defaultdict(int)
    for tag in Tag.objects.all():
        for item in tag.item_set.all():
            uses_by_pk[tag.pk] += 1

    hit_counts = sorted((value, key) for (key,value) in uses_by_pk.items())
    hit_counts.reverse()

    return hit_counts
