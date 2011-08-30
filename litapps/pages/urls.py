from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('litapps.pages.views',

    # Front page
    url(r'^$', 'front_page', name='lit-main-page'),

    # About page
    url(r'about', 'about_page', name='lit-about-page'),

    # Search views (go through our app to log search queries)
    #url(r'search', 'search', name='haystack_search'),

)