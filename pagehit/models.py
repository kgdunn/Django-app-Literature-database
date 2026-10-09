from django.db import models


class PageHit(models.Model):
    """Records each hit (page view) of a surface in the literature catalogue.

    Two kinds of row land here, keyed by the ``item`` column (see
    ``pagehit.views.create_hit``):

    - ``item="item"`` for an ``Item`` detail-page view; ``item_pk`` is
      the real ``Item.pk`` from ``items_item``.
    - One of the static-surface keys enumerated in
      ``pagehit.views.static_items`` (``lit-main-page``,
      ``haystack_search``, ``lit-about-page``, the ``lit-tag-page`` /
      ``lit-author-page`` / ``lit-year-page`` / ``lit-journal-page``
      landing pages, and the ``lit-show-all-items`` /
      ``lit-show-all-tags`` listings) for the shared pages; ``item_pk``
      is the sentinel negative that keeps those surfaces distinct in
      the admin's ``list_filter`` and ``date_hierarchy`` without
      colliding with a real ``Item.pk``.

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
