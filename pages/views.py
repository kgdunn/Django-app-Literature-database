import logging

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
)
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import get_template

from items.models import Item
from pagehit.views import create_hit
from utils import get_IP_address, paginated_queryset

logger = logging.getLogger(__name__)


def front_page(request):
    """Assembles the front page with predefined defaults.

    `years` powers the front-page "Browse by year" navigation: the 15
    most recent publication years, each with the count of items in
    that year. ORDER BY year DESC so the list is human-readable.
    """
    years = (
        Item.objects.values('year')
        .annotate(count=Count('id'))
        .order_by('-year')[:15]
    )
    return render(request, 'pages/front-page.html', {
        'latest_items': Item.latest_items.get_latest(n=10),
        'years': list(years),
    })


def healthz(request):
    """Liveness probe consumed by the Dockerfile HEALTHCHECK and the
    Phase-9 deploy script. Plain text, never cached, no DB hit so a
    Postgres outage doesn't fail the container's healthcheck.
    """
    response = HttpResponse('ok', content_type='text/plain')
    response['Cache-Control'] = 'no-store'
    return response


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
    """Site-wide search.

    Postgres full-text search: weighted ``SearchVector`` over title /
    abstract / other_search_text, ranked by ``SearchRank``, OR-joined
    with ``__trigram_similar`` on author last names so typos still
    find the right author. Backed by the ``pg_trgm`` extension
    (installed in ``items`` migration 0004).

    Both dev and prod settings point at Postgres (Phase 3 onwards), so
    this view does not branch on ``connection.vendor`` — Postgres is
    the only supported backend.
    """
    q = request.GET.get('q', '').strip()
    if not q:
        return redirect(front_page)

    # Numeric query is treated as a direct item-id shortcut: if it
    # resolves, redirect; otherwise fall through to text search so a
    # query like "2023" still finds papers.
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

    vector = (
        SearchVector('title', weight='A', config='english')
        + SearchVector('abstract', weight='B', config='english')
        + SearchVector('other_search_text', weight='C', config='english')
    )
    # `websearch` parses the user input forgivingly: bare terms ANDed,
    # quoted phrases preserved, `-foo` excludes.
    query = SearchQuery(q, config='english', search_type='websearch')

    # Threshold of 0.3 catches one-letter typos in author last names
    # (`einstien` -> `Einstein`) without sweeping in unrelated names.
    # Tunable here without touching the per-session pg_trgm GUC.
    AUTHOR_TRIGRAM_THRESHOLD = 0.3

    results = (
        Item.objects
        .annotate(
            rank=SearchRank(vector, query),
            author_sim=TrigramSimilarity('authorgroup__author__last_name', q),
        )
        .filter(Q(rank__gt=0) | Q(author_sim__gt=AUTHOR_TRIGRAM_THRESHOLD))
        .order_by('-rank', '-author_sim', '-year')
        .distinct()
    )

    entries = paginated_queryset(request, results)

    return render(request, 'pages/search.html', {
        'query': q,
        'entries': entries,
        'no_entries_message': 'No items match "%s".' % q,
    })
