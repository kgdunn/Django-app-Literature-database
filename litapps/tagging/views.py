import models
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
    for tag in models.Tag.objects.all():
        for item in tag.item_set.all():
            uses_by_pk[tag.pk] += 1

    # Finally, create a list of hit counts, which can be used for sorting
    hit_counts = []
    for key, val in uses_by_pk.iteritems():
        hit_counts.append((val, key))

    return hit_counts
