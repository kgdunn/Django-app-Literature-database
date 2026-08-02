import logging

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramSimilarity
from django.db.models import Count, Max, Q
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
    create_hit(request, "lit-main-page")
    years = Item.objects.values("year").annotate(count=Count("id")).order_by("-year")[:15]
    return render(
        request,
        "pages/front-page.html",
        {
            "latest_items": Item.latest_items.get_latest(n=10),
            "years": list(years),
        },
    )


def healthz(request):
    """Liveness probe consumed by the Dockerfile HEALTHCHECK and the
    Phase-9 deploy script. Plain text, never cached, no DB hit so a
    Postgres outage doesn't fail the container's healthcheck.
    """
    response = HttpResponse("ok", content_type="text/plain")
    response["Cache-Control"] = "no-store"
    return response


# Issue #72: keep search engines out of the admin / accounts / extract
# endpoints. Anyone who guesses the URLs can still hit them — this
# only stops them from being surfaced via Google. The staging site
# (`test.literature.learnche.org`) gets a separate full-site
# ``X-Robots-Tag: noindex, nofollow`` via SecurityHeadersMiddleware
# when ``LITERATURE_NOINDEX=true`` is set in its ``.env``.
ROBOTS_TXT = """User-agent: *
Disallow: /admin/
Disallow: /accounts/
Disallow: /__extract_extra__/
"""


def robots_txt(request):
    """Serve ``/robots.txt`` directly from Django so the file lives in
    the repo and tracks the URL surface — Caddy doesn't need a custom
    rule beyond the existing reverse proxy."""
    return HttpResponse(ROBOTS_TXT, content_type="text/plain")


def about_page(request):
    create_hit(request, "lit-about-page")
    return render(request, "pages/about-page.html")


def page_404_error(request, exception=None, extra_info=""):
    """Override Django's 404 handler, because we want to log this also.

    Django's handler signature changed in 1.9 to add `exception`; we accept
    it here so the handler is callable both directly (where we pass
    extra_info) and via the URL resolver.

    ``extra_info`` is an optional human-readable message threaded into the
    404 template's context, letting direct callers give a richer
    explanation than Django's bare ``Resolver404``. When it is empty the
    context falls back to ``str(exception)``.
    """
    ip = get_IP_address(request)
    info = extra_info or (str(exception) if exception is not None else "")
    logger.info('404 from %s for request "%s"; extra info=%s', ip, request.path, info)
    t = get_template("404.html")
    html = t.render({"extra_info": info}, request)
    return HttpResponse(html, status=404)


def page_500_error(request):
    """Override Django's 500 handler, because we want to log this also."""
    ip = get_IP_address(request)
    logger.error('500 from %s for request "%s"', ip, request.path)
    t = get_template("500.html")
    html = t.render({}, request)
    return HttpResponse(html, status=500)


def search(request):
    """Site-wide search.

    Postgres full-text search: weighted ``SearchVector`` over the base
    ``Item`` fields (``title`` A, ``abstract`` B, ``other_search_text`` C)
    *plus* the subclass-specific fields joined in for issue #33
    (``journalpub__journal__name``, ``book__isbn``,
    ``conferenceproceeding__conference_name``,
    ``conferenceproceeding__organization``,
    ``conferenceproceeding__location``, ``incollection__book_title``),
    ranked by ``SearchRank``, OR-joined
    with ``__trigram_similar`` on author last names so typos still
    find the right author. Backed by the ``pg_trgm`` extension
    (installed in ``items`` migration 0004).

    Both dev and prod settings point at Postgres (Phase 3 onwards), so
    this view does not branch on ``connection.vendor`` — Postgres is
    the only supported backend.
    """
    q = request.GET.get("q", "").strip()
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
            return redirect("lit-view-item", item_id=item_id)

    # Avoid duplicate logging if the search request paginates.
    if "page" not in request.GET:
        create_hit(request, "haystack_search", extra_info=q)
        logger.info("SEARCH [%s]: %s", get_IP_address(request), q)

    # Issue #33: include subclass-specific fields so a query like
    # "Analytica" (the journal) or an ISBN finds the relevant items
    # even though those strings live on the JournalPub / Book /
    # ConferenceProceeding tables, not on the parent Item. Each Item
    # is at most one subclass; the LEFT JOINs to the others produce
    # NULLs that SearchVector coalesces to empty strings (so
    # non-matching subclasses contribute nothing to the row's vector).
    vector = (
        SearchVector("title", weight="A", config="english")
        + SearchVector("abstract", weight="B", config="english")
        + SearchVector("other_search_text", weight="C", config="english")
        + SearchVector("journalpub__journal__name", weight="B", config="english")
        + SearchVector("book__isbn", weight="C", config="english")
        + SearchVector("conferenceproceeding__conference_name", weight="B", config="english")
        + SearchVector("conferenceproceeding__organization", weight="C", config="english")
        + SearchVector("conferenceproceeding__location", weight="C", config="english")
        + SearchVector("incollection__book_title", weight="B", config="english")
    )
    # `websearch` parses the user input forgivingly: bare terms ANDed,
    # quoted phrases preserved, `-foo` excludes.
    query = SearchQuery(q, config="english", search_type="websearch")

    # Threshold of 0.3 catches one-letter typos in author last names
    # (`einstien` -> `Einstein`) without sweeping in unrelated names.
    # Tunable here without touching the per-session pg_trgm GUC.
    AUTHOR_TRIGRAM_THRESHOLD = 0.3

    results = (
        Item.objects.annotate(
            # cover_density=True switches the underlying Postgres function
            # from ts_rank (term-frequency) to ts_rank_cd (cover-density,
            # i.e. proximity-aware). Without it an exact phrase in the
            # title — weight A, single occurrence — was outranked by a
            # different paper whose other_search_text (weight C, extracted
            # PDF body) repeated the same terms dozens of times. Issue #15.
            rank=SearchRank(vector, query, cover_density=True),
            # Max() collapses the AuthorGroup→Author join from N rows
            # (one per author) to one row per Item: the max trigram
            # similarity across the item's authors. Without this a
            # 3-author paper rendered 3× in the results because each
            # joined row carried a different ``author_sim`` value and
            # ``.distinct()`` couldn't dedupe. The implicit ``GROUP BY
            # items_item.id`` also makes the trailing ``.distinct()``
            # redundant — dropped.
            author_sim=Max(TrigramSimilarity("authorgroup__author__last_name", q)),
        )
        .filter(Q(rank__gt=0) | Q(author_sim__gt=AUTHOR_TRIGRAM_THRESHOLD))
        .order_by("-rank", "-author_sim", "-year")
    )

    entries = paginated_queryset(request, results)

    return render(
        request,
        "pages/search.html",
        {
            "query": q,
            "entries": entries,
            "no_entries_message": 'No items match "%s".' % q,
        },
    )
