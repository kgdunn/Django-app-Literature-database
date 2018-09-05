from django.conf.urls import url, include, static
from django.conf import settings



# Enable the admin:
from django.contrib import admin
admin.autodiscover()


urlpatterns = [
    url(r'^admin/', admin.site.urls),

    # Major pages in the site: front page, about page, search, etc
    url(r'', include('pages.urls')),

    # Submissions: new and existing, including previous revisions
    url(r'item/', include('items.urls')),

    ## Tagging
    #(r'^tagging/', include('tagging.urls')),

]

handler404 = 'pages.views.page_404_error'
handler500 = 'pages.views.page_500_error'


urlpatterns += static.static(settings.MEDIA_URL,
                             document_root=settings.MEDIA_ROOT)