import logging

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import get_template

from items.models import Item
from pagehit.views import create_hit
from utils import get_IP_address

logger = logging.getLogger(__name__)


def front_page(request):
    """Assembles the front page with predefined defaults"""
    return render(request, 'pages/front-page.html',
                  {'latest_items': Item.latest_items.get_latest(n=10)})


def about_page(request):
    return render(request, 'pages/about-page.html')


def page_404_error(request, exception=None, extra_info=''):
    """ Override Django's 404 handler, because we want to log this also.

    Django's handler signature changed in 1.9 to add `exception`; we accept
    it here so the handler is callable both directly (where we pass
    extra_info) and via the URL resolver.
    """
    ip = get_IP_address(request)
    info = extra_info or (str(exception) if exception is not None else '')
    logger.info('404 from %s for request "%s"; extra info=%s',
                ip, request.path, info)
    t = get_template('404.html')
    html = t.render({'extra_info': info}, request)
    return HttpResponse(html, status=404)


def page_500_error(request):
    """ Override Django's 500 handler, because we want to log this also.
    """
    ip = get_IP_address(request)
    logger.error('500 from %s for request "%s"', ip, request.path)
    t = get_template('500.html')
    html = t.render({}, request)
    return HttpResponse(html, status=500)


def search(request):
    """
    Site-wide search.

    Phase 1 stub: the legacy implementation called Haystack on a
    Whoosh / Xapian backend, which doesn't run on Python 3 / Django 5.2.
    Haystack and its templates will be removed in Phase 3 and this view
    will be rewritten to use ``django.contrib.postgres.search``
    (SearchVector / SearchRank / TrigramSimilarity) so the same URL keeps
    working without an external search service. Until that lands, the
    search view does an item-id shortcut and otherwise renders an
    explanatory page so the route doesn't 500.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return redirect(front_page)

    # Numeric query → direct item-id shortcut.
    try:
        item_id = int(q)
    except ValueError:
        pass
    else:
        if Item.objects.filter(id=item_id).exists():
            return redirect('lit-view-item', item_id=item_id)

    # Avoid duplicate logging if the search request paginates.
    if 'page' not in request.GET:
        create_hit(request, 'haystack_search', extra_info=q)
        logger.info('SEARCH [%s]: %s', get_IP_address(request), q)

    # Phase-3 placeholder. Render the front-page template so visitors
    # land somewhere sensible with the latest items still browseable.
    return render(request, 'pages/front-page.html', {
        'latest_items': Item.latest_items.get_latest(n=10),
        'search_disabled_query': q,
    })
