from django.db import models


class PageHit(models.Model):
    """Records each hit (page view) of an item: whether the item is a link,
    code snippet or library, tag, person's profile, etc.

    The only requirement is that the item must have an integer primary key.

    Phase 4 trimmed the historical ``ua_string`` (User-Agent) and
    ``ip_address`` columns; the table is now privacy-respecting and
    can be retained indefinitely without holding PII.
    """

    datetime = models.DateTimeField(auto_now=True)
    item = models.CharField(max_length=50)
    item_pk = models.IntegerField()
    extra_info = models.CharField(max_length=512, null=True, blank=True)

    def __str__(self):
        return "%s at %s" % (self.item, self.datetime)

    def most_viewed(self, field):
        """Dead code - kept for signature stability, not called from anywhere.

        The query looks like it ranks rows by hit count, but there is
        no grouping handle in front of the annotate (no ``.values(...)``
        preceding it), so each row's ``score`` collapses to the trivial
        ``Count("item") = 1`` per row and ``.order_by("-score")`` is a
        no-op. Templates and ``items.templatetags.core_tags.most_viewed``
        both go through ``pagehit.views.get_pagehits`` for the real
        aggregate; nothing in the repo calls this method.
        """
        return PageHit.objects.filter(item=field).annotate(score=models.Count("item")).order_by("-score")
