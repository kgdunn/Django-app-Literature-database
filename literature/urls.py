from django.conf.urls.defaults import patterns, include, url
from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()


urlpatterns = [
    url(r'^admin/', admin.site.urls),
]




#urlpatterns = patterns('',
    ## Examples:
    ## url(r'^$', 'deploy.views.home', name='home'),
    ## url(r'^deploy/', include('deploy.foo.urls')),

    ## Uncomment the next line to enable the admin:
    #url(r'^admin/', include(admin.site.urls)),

    ## Include the URLs for the website
    #url(r'', include('litapps.urls')),
#)

handler404 = 'litapps.pages.views.page_404_error'
handler500 = 'litapps.pages.views.page_500_error'

if settings.DEBUG:
    # Small problem: cannot show 404 templates /media/....css file, because
    # 404 gets overridden by Django when in debug mode
    urlpatterns += patterns(
        '',
        (r'^media/(?P<path>.*)$',
         'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    )
