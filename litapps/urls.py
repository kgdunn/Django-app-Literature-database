from django.conf.urls.defaults import url, include, patterns
urlpatterns = patterns('litapps',

    # Major pages in the site: front page, about page, search, etc
    #url(r'', include('litapps.pages.urls')),

    # Submissions: new and existing, including previous revisions
    url(r'item/', include('litapps.items.urls')),

    # Tagging
    (r'^tagging/', include('litapps.tagging.urls')),

)
