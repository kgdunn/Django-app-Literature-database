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
        """Most viewed in terms of a certain item."""
        return PageHit.objects.filter(item=field).annotate(score=models.Count("item")).order_by("-score")
