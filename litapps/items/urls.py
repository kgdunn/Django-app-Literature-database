from django.conf.urls.defaults import url, patterns

urlpatterns = patterns('litapps.items.views',

    # SHOW ITEMS in different ways
    # ============================
    url(r'^(?P<what_view>[a-zA-Z]+)/(?P<extra_info>.+)/$', 'show_items',
                                                       name='lit-show-items'),

    # Download an item (this URL must come before the next URL rule; also see
    url(r'^(?P<item_id>\d+)/download/$', 'download_item', name='lit-download-pdf'),

    # View an existing item: both versions of accessing the item are valid
    # Maximum information:   http://..../23/draw-an-ellipse/
    # Minimal working link:  http://..../23/    <-- shows latest revision
    url(r'^(?P<item_id>\d+)+(/)?(?P<slug>[-\w]+)?(/)?',
                                           'view_item', name='lit-view-item'),
)
