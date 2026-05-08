from django.urls import re_path

from items.views import __extract_extra__, show_items, view_item

urlpatterns = [

    re_path(r'^show-all$',
            show_items,
            {'what_view': 'all'},
            name='show-items--all'),

    re_path(r'^pub-by-year/(?P<extra_info>.+)/$',
            show_items,
            {'what_view': 'pub-by-year'},
            name='show-items--pub-by-year'),

    # SHOW ITEMS in different ways
    # ============================
    re_path(r'^(?P<what_view>[-a-zA-Z]+)/(?P<extra_info>.+)/$',
            show_items,
            name='lit-show-items'),

    # View an existing item: both versions of accessing the item are valid
    # Maximum information:   http://..../23/draw-an-ellipse/
    # Minimal working link:  http://..../23/    <-- shows latest revision
    #
    # NOTE: Phase 5 removed the public PDF download URL (`download.pdf`)
    # because all PDFs are copyright-restricted. PDFs are admin-only
    # storage, consumed by `__extract_extra__` for FTS text extraction.
    re_path(r'^(?P<item_id>\d+)+(/)?(?P<slug>[-\w]+)?(/)?',
            view_item,
            name='lit-view-item'),

    # Extract PDF text to add to the Item object (admin-only).
    re_path(r'__extract_extra__/(?P<item_id>\d+)',
            __extract_extra__,
            name='lit-extract-extra'),
]
