from django.urls import re_path

from items.views import __extract_extra__, show_items, view_item, view_pdf

urlpatterns = [
    re_path(r"^show-all$", show_items, {"what_view": "all"}, name="show-items--all"),
    re_path(
        r"^pub-by-year/(?P<extra_info>.+)/$",
        show_items,
        {"what_view": "pub-by-year"},
        name="show-items--pub-by-year",
    ),
    # SHOW ITEMS in different ways
    # ============================
    re_path(
        r"^(?P<what_view>[-a-zA-Z]+)/(?P<extra_info>.+)/$",
        show_items,
        name="lit-show-items",
    ),
    # Gated public PDF. Phase 5 removed the *unconditional* `download.pdf`
    # endpoint (all PDFs were copyright-restricted). This route restores a
    # narrow, default-off path: `view_pdf` serves the bytes ONLY when an
    # admin has ticked `Item.pdf_is_public` for that item, otherwise it
    # 404s. Must precede the `lit-view-item` catch-all below so `/item/<id>/pdf`
    # doesn't get swallowed as a slug.
    re_path(r"^(?P<item_id>\d+)/pdf/?$", view_pdf, name="lit-public-pdf"),
    # View an existing item: both URL shapes resolve to the same item.
    # Canonical shape:   http://..../23/draw-an-ellipse/
    # Minimal shape:     http://..../23/    <-- get_items_or_404 issues a
    #                                           permanent redirect to the
    #                                           canonical /<id>/<slug>/ form.
    re_path(r"^(?P<item_id>\d+)+(/)?(?P<slug>[-\w]+)?(/)?", view_item, name="lit-view-item"),
    # Extract PDF text to add to the Item object (admin-only).
    re_path(
        r"__extract_extra__/(?P<item_id>\d+)",
        __extract_extra__,
        name="lit-extract-extra",
    ),
]
