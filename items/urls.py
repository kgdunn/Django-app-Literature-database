from django.conf.urls import url
from items.views import show_items, download_item, view_item, __extract_extra__

urlpatterns = [

    url(r'^show-all$',
        show_items,
        {'what_view': 'all'},
        name='show-items--all'),

    url(r'^pub-by-year/(?P<extra_info>.+)/$',
        show_items,
        {'what_view': 'pub-by-year'},
        name='show-items--pub-by-year'),



    # SHOW ITEMS in different ways
    # ============================
    url(r'^(?P<what_view>[-a-zA-Z]+)/(?P<extra_info>.+)/$',
        show_items,
        name='lit-show-items'),

    # Download an item (this URL must come before the next URL rule; also see
    url(r'^(?P<item_id>\d+)/download.pdf$',
        download_item,
        name='lit-download-pdf'),

    # View an existing item: both versions of accessing the item are valid
    # Maximum information:   http://..../23/draw-an-ellipse/
    # Minimal working link:  http://..../23/    <-- shows latest revision
    url(r'^(?P<item_id>\d+)+(/)?(?P<slug>[-\w]+)?(/)?',
        view_item,
        name='lit-view-item'),


    # Extract PDF text to add to the Item object
    url(r'__extract_extra__/(?P<item_id>\d+)',
        __extract_extra__,
        name='lit-extract-extra'),
]