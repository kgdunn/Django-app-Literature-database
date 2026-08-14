import logging
import re

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.defaultfilters import slugify

from items.models import Author, Book, ConferenceProceeding, InCollection, Item, Journal, JournalPub, Thesis
from pagehit.views import create_hit
from pages.views import page_404_error
from tagging.models import Tag
from utils import paginated_queryset

logger = logging.getLogger(__name__)


def _track_hit(request, item_key, slug=""):
    """Record a PageHit for a tag / author / year / journal landing page,
    or for one of the static "all" listings. Skipped on paginated requests
    (``?page=…``) so a user clicking through the result list doesn't
    inflate the visit count for that landing page — same convention used
    by ``pages.search``."""
    if "page" in request.GET:
        return
    create_hit(request, item_key, extra_info=slug)


def _year_count_series(items_qs):
    """Year → article-count distribution for a filtered Items queryset.

    Issue #27: powers the small inline-SVG sparkline rendered above the
    entries list on tag/author landing pages. Returns a list of
    ``(year, count)`` tuples ordered by year ascending — empty list if
    no items.
    """
    return list(items_qs.values("year").annotate(count=Count("id")).order_by("year").values_list("year", "count"))


def _get_related_items(item, limit=5):
    """Items most similar to ``item`` by FTS overlap on title + abstract.

    Issue #36 — cheap precursor to the Phase-12 pgvector "Similar
    papers" panel. Tokenizes the current item's title + abstract into
    alpha words ≥4 chars (filters most English stop words), caps at
    20 words to keep the parse tree bounded, and OR-joins them as
    individual ``plain`` SearchQuery objects. Cover-density ranking
    then rewards items with multiple overlapping terms clustered
    close together. Returns the top non-zero matches.

    OR semantics matter here: a websearch-style AND of every word
    would require *all* words to match, so a sibling paper missing
    one or two would rank zero and disappear from the panel.

    Returns ``[]`` for empty title+abstract, no extractable words
    after filtering, or no overlap with any other item.
    """
    query_text = ((item.title or "") + " " + (item.abstract or "")).strip()
    if not query_text:
        return []
    # Alpha-only, ≥4 chars, deduped, capped at 20 — drops most English
    # stop words and keeps the OR-tree bounded.
    words = re.findall(r"[a-zA-Z]{4,}", query_text.lower())
    words = list(dict.fromkeys(words))[:20]
    if not words:
        return []
    query = SearchQuery(words[0], config="english", search_type="plain")
    for w in words[1:]:
        query = query | SearchQuery(w, config="english", search_type="plain")
    vector = SearchVector("title", weight="A", config="english") + SearchVector(
        "abstract", weight="B", config="english"
    )
    return list(
        Item.objects.exclude(pk=item.pk)
        .annotate(rank=SearchRank(vector, query, cover_density=True))
        .filter(rank__gt=0)
        .order_by("-rank")[:limit]
    )


def _adjacent_years_with_items(current_year):
    """Closest years (below and above ``current_year``) that have at
    least one Item. Issue #17 — powers the prev/next year navigation
    on ``/item/pub-by-year/<year>/``. Returns ``(prev_year, next_year)``
    where either side may be ``None`` if no such year exists.
    """
    other_years = list(Item.objects.values_list("year", flat=True).distinct().order_by("year"))
    prev_year = max((y for y in other_years if y < current_year), default=None)
    next_year = min((y for y in other_years if y > current_year), default=None)
    return prev_year, next_year


def get_items_or_404(view_function):
    """
    Decorator that resolves an ``Item`` from ``item_id`` and downcasts
    it to its concrete subclass (JournalPub / Book / ConferenceProceeding
    / Thesis / InCollection based on ``item_type``). 404s if no Item
    matches; otherwise redirects (permanent) to the canonical
    ``/item/<id>/<slug>`` URL when the slug is missing or wrong.

    Phase 5 removed the ``download.pdf`` branch on this decorator.
    ``view_item`` is now the only view that uses it. The gated
    ``view_pdf`` endpoint (v1.4.0, ``Item.pdf_is_public``) does its own
    item lookup and does not go through this decorator.
    """

    def decorator(request, item_id, slug=None):
        try:
            the_item = Item.objects.all().filter(id=item_id)
        except ObjectDoesNotExist:
            return page_404_error(request, "You request a non-existant item")

        if len(the_item) == 0:
            return page_404_error(request, "This item does not exist yet")

        the_item = the_item[0]

        # Is the URL not the canonical URL for the item? Redirect the user.
        if slug is None or the_item.slug != slug:
            return redirect("/".join(["/item", str(item_id), the_item.slug]), permanent=True)

        if the_item.item_type == "conferenceproc":
            the_item = ConferenceProceeding.objects.get(id=item_id)
        if the_item.item_type == "thesis":
            the_item = Thesis.objects.get(id=item_id)
        if the_item.item_type == "journalpub":
            the_item = JournalPub.objects.get(id=item_id)
        if the_item.item_type == "book":
            the_item = Book.objects.get(id=item_id)
        if the_item.item_type == "incollection":
            the_item = InCollection.objects.get(id=item_id)

        return view_function(request, the_item, slug)

    return decorator


def show_items(request, what_view="", extra_info=""):
    """
    Shows a paginated list of items.

    Dispatches on ``what_view`` to pick the queryset and page layout:

    - ``"tag"`` - items carrying ``Tag.slug == slugify(extra_info)``.
    - ``"author"`` - items co-authored by ``Author`` with the matching slug.
    - ``"journal"`` - items published in the ``Journal`` with the matching slug.
    - ``"pub-by-year"`` - items whose ``year == int(extra_info)``.
    - ``"show"`` + ``"all-tags"`` / ``"all-items"``, or ``"all"`` - full
      listing branches (tag cloud / every item).

    ``extra_info`` carries the per-branch filter value (slug or year).
    Anything unrecognised falls through to an empty page.
    """
    what_view = what_view.lower()
    extra_info = extra_info.lower()
    # Slug captured before the per-branch `extra_info` rewrites below
    # decorate it for display ('"foo"' / 'foo: "bar"' / etc). Keep the
    # raw slug for the PageHit row so analytics can group cleanly.
    hit_slug = extra_info
    entry_order = []
    page_title = ""
    template_name = "items/show-entries.html"
    description = ""
    sparkline_data = []  # Issue #27: only populated for tag/author branches
    prev_year = None  # Issue #17: only populated for pub-by-year branch
    next_year = None
    if what_view == "tag":
        _track_hit(request, "lit-tag-page", hit_slug)
        # Issue #12: surface the tag's description on its own results
        # page when one is set. Falls through to "" (template skips
        # rendering the block) when the tag has no description, the
        # slug doesn't resolve to a Tag at all (legacy data), or the
        # tag exists but description is None.
        tag = Tag.objects.filter(slug=slugify(hit_slug)).first()
        description = (tag.description if tag else "") or ""
        all_items = Item.objects.all().filter(tags__slug=slugify(extra_info))
        sparkline_data = _year_count_series(all_items)
        page_title = "All entries tagged"
        extra_info = ': "%s"' % extra_info
        entry_order = list(all_items)

    elif what_view == "show" and extra_info == "all-tags":
        _track_hit(request, "lit-show-all-tags")
        page_title = "All tags"
        template_name = "items/show-tag-cloud.html"

    elif (what_view == "show" and extra_info == "all-items") or what_view == "all":
        # Two URL shapes land here:
        #   /item/show-all       (legacy, ``what_view='all'``, no extra_info)
        #   /item/show/all-items (regex ``lit-show-items``, ``what_view='show'``)
        # Pre-PR the legacy shape silently fell through every branch and
        # rendered an empty page. Treat them identically.
        _track_hit(request, "lit-show-all-items")
        all_items = Item.objects.all().order_by("-year")
        page_title = "All items in our database "
        extra_info = "(reverse publication date order)"
        entry_order = list(all_items)

    elif what_view == "pub-by-year":
        _track_hit(request, "lit-year-page", hit_slug)
        all_items = Item.objects.all().filter(year=extra_info)
        # Issue #17: prev/next year navigation. Closest neighbours that
        # actually have at least one item.
        try:
            current_year_int = int(hit_slug)
        except (TypeError, ValueError):
            current_year_int = None
        if current_year_int is not None:
            prev_year, next_year = _adjacent_years_with_items(current_year_int)
        page_title = "All entries published in "
        extra_info = "%s" % extra_info
        entry_order = list(all_items)

    elif what_view == "author":
        author = Author.objects.filter(slug=extra_info)
        if len(author) == 0:
            return page_404_error(request, 'There are no publications by "%s"' % extra_info)

        _track_hit(request, "lit-author-page", hit_slug)
        author_items = Item.objects.all().filter(authors__slug=extra_info)
        sparkline_data = _year_count_series(author_items)
        page_title = "All entries by author"
        extra_info = ' "%s"' % author[0].full_name
        entry_order = list(author_items)

    elif what_view == "journal":
        journal = Journal.objects.filter(slug=extra_info)
        if len(journal) == 0:
            return page_404_error(request, 'There are no publications in "%s"' % extra_info)

        _track_hit(request, "lit-journal-page", hit_slug)
        journal_items = JournalPub.objects.all().filter(journal=journal[0])
        page_title = "All entries in "
        extra_info = ' "%s"' % journal[0].name
        entry_order = list(journal_items)

    entries = paginated_queryset(request, entry_order)
    return render(
        request,
        template_name,
        {
            "entries": entries,
            "page_title": page_title,
            "extra_info": extra_info,
            "description": description,
            "sparkline_data": sparkline_data,
            "prev_year": prev_year,
            "next_year": next_year,
        },
    )


@get_items_or_404
def view_item(request, the_item, slug):
    """
    Show the full details of one item.

    Phase 5 removed the unconditional public PDF download for copyright
    reasons; v1.4.0 reintroduced a narrow, default-off path. The template
    renders a "View PDF" link — pointing at the gated ``view_pdf`` view
    (URL name ``lit-public-pdf``) — only when both ``item.pdf_is_public``
    and ``item.pdf_file`` are set; every other item stays default-deny and
    simply omits the link. The page also surfaces citation, abstract,
    DOI / external link, tags, and a "Related items" panel (issue #36).
    """
    logger.debug("Viewing: %s", the_item)

    create_hit(request, the_item.pk)
    return render(
        request,
        "items/item.html",
        {
            "item": the_item,
            "tag_list": the_item.tags.all(),
            "related_items": _get_related_items(the_item, limit=5),
        },
    )


def view_pdf(request, item_id):
    """Serve an Item's PDF inline — but ONLY when an admin has explicitly
    ticked ``Item.pdf_is_public`` for that item.

    Default-deny: ``pdf_is_public`` defaults to False, so every item is
    non-downloadable until an admin opts it in (used for the handful of
    genuinely public / open-access documents in the catalogue). Items
    without the flag — or without a PDF at all — 404 here. In production
    Caddy independently 404s direct ``/media/literature/pdf/*`` access, so
    this view (running in the gunicorn worker) is the single gate that can
    open a copyright-cleared PDF to the public.
    """
    item = Item.objects.filter(id=item_id).first()
    if item is None or not item.pdf_is_public or not item.pdf_file:
        raise Http404("No public PDF is available for this item.")
    return FileResponse(
        item.pdf_file.open("rb"),
        as_attachment=False,
        filename="%s.pdf" % item.slug,
        content_type="application/pdf",
    )


def __extract_extra__(request, item_id=None):
    """
    Admin-only, idempotent backfill that extracts plain text from each
    Item's PDF via ``pdfplumber`` and stores it in ``Item.other_search_text``
    so the Postgres-FTS search vector (Phase 3) can index it. Replaces the
    legacy ``pdfminer`` chain.

    Gated on ``request.user.is_authenticated`` — an unauthenticated caller
    gets a plain-text "Please sign in first" body.

    Idempotent by design: for each Item in scope, the extractor skips items
    that already have ``other_search_text`` populated (so re-running is
    cheap) and skips items with no ``pdf_file`` attached (nothing to
    extract from). Scope is either a single item (when ``item_id`` is in the
    URL) or every Item in the catalogue (bare ``/__extract_extra__/``).

    Fails closed on the first pdfplumber exception: the currently-open PDF
    is logged and the whole traversal short-circuits with a 200-status
    ``FAILED in completely PDF index "<title>"`` body rather than
    partial-index silently. Successfully-extracted items are ``save()``d
    one at a time so a mid-run failure keeps whatever has already been
    written.
    """
    if not request.user.is_authenticated:
        return HttpResponse("Please sign in first")

    import pdfplumber

    if item_id:
        all_items = Item.objects.filter(id=item_id)
    else:
        all_items = Item.objects.all()

    last_title = ""
    for item in all_items:
        # Don't extract if no PDF exists; or if we already have search text.
        if not item.pdf_file or item.other_search_text:
            continue

        last_title = item.title
        try:
            with pdfplumber.open(item.pdf_file.path) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
        except Exception:  # pdfplumber raises a broad set of errors
            logger.warning('FAILED in completely PDF index "%s"', item.title)
            return HttpResponse('FAILED in completely PDF index "%s"' % item.title)

        item.other_search_text = "\n".join(pages)
        item.save()
        logger.debug('Full PDF index of item "%s"', item.title)

    return HttpResponse('Full PDF indexed for item "%s"' % last_title)
