from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, re_path

urlpatterns = [
    re_path(r"^admin/", admin.site.urls),
    # Major pages in the site: front page, about page, search, etc.
    re_path(r"", include("pages.urls")),
    # Submissions: new and existing, including previous revisions.
    re_path(r"item/", include("items.urls")),
]

handler404 = "pages.views.page_404_error"
handler500 = "pages.views.page_500_error"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
