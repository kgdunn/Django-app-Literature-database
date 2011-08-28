from django.conf.urls.defaults import url, include, patterns
urlpatterns = patterns('litapps.items.views',


    # Submissions: new and existing, including previous revisions
    url(r'show', 'show', name='lit-items'),

)
