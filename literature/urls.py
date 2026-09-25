from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import Http404
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


def _block_media_pdf(request, *args, **kwargs):
    """Hard 404 for any direct hit on the copyright-restricted PDF subtree.

    Defence-in-depth: the on-disk path is the guessable
    ``literature/pdf/<slug[0]>/<slug>.pdf`` shape (the slug comes straight
    off the public title), so a visitor who downloads one *public* PDF could
    otherwise reconstruct the media URL for a *non-public* item. The only
    sanctioned way to read a PDF is the gated ``items.view_pdf`` view, which
    checks ``Item.pdf_is_public`` first.

    This view is only wired into ``urlpatterns`` inside the ``if
    settings.DEBUG:`` block below, i.e. in local dev where Django's
    ``static()`` helper would otherwise let runserver serve
    ``/media/literature/pdf/*`` off disk. In staging and production
    (``DEBUG=False``), Django does not serve ``/media/*`` at all - Caddy
    does, and its server block issues its own ``respond
    /media/literature/pdf/* 404``. Between the two, no PDF is reachable
    outside ``view_pdf`` in any environment.
    """
    raise Http404("Not available")


if settings.DEBUG:
    # The block MUST precede ``static()`` so runserver's media file_server
    # never gets a chance to serve the PDF subtree.
    urlpatterns += [re_path(r"^media/literature/pdf/", _block_media_pdf)]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
