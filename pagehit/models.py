from django.db import models


class PageHit(models.Model):
    """Append-only view-counter for the literature site.

    One row per rendered page. Two shapes of hit share the same table:

    - **Item detail hits** — ``item="item"`` with ``item_pk`` set to the
      real ``Item.pk`` (written by ``items.views.view_item`` via
      ``pagehit.views.create_hit``).
    - **Static-surface hits** — one of the fixed keys enumerated in
      ``pagehit.views.static_items``: ``lit-main-page`` (front page),
      ``haystack_search`` (search — key preserved from the pre-Phase-3
      Haystack era), ``lit-about-page`` (about), ``lit-show-all-items``
      (full item listing), ``lit-show-all-tags`` (tag cloud),
      ``lit-tag-page`` / ``lit-author-page`` / ``lit-year-page`` /
      ``lit-journal-page`` (per-tag / per-author / per-year / per-journal
      landing pages). Each carries a sentinel negative ``item_pk`` so
      the admin's ``date_hierarchy`` / ``list_filter`` group cleanly by
      surface.

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
        """Return a queryset of ``PageHit`` rows for the given ``item``
        category, annotated with a per-row ``score`` count and ordered
        highest-first.

        ``field`` is matched against the ``item`` column (e.g. ``"item"``
        for item-detail hits, or one of the static-surface keys listed
        on the class). The bound-method signature ignores ``self``:
        the method is called from templates via
        ``items/templatetags/core_tags.py``, which needs a filter that
        accepts a value, and instantiating a throwaway ``PageHit`` is
        cheaper than routing around Django's template tag system.

        Note: the returned queryset annotates each row individually
        (no ``GROUP BY``), so it is one row per stored ``PageHit``
        rather than one row per distinct ``item_pk``. Callers that want
        per-item aggregates should use ``pagehit.views.get_pagehits``
        instead.
        """
        return PageHit.objects.filter(item=field).annotate(score=models.Count("item")).order_by("-score")
