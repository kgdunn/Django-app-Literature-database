import logging

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.defaultfilters import slugify

from items.models import (
    Author,
    Book,
    ConferenceProceeding,
    Item,
    Journal,
    JournalPub,
    Thesis,
)
from pagehit.views import create_hit
from pages.views import page_404_error
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


def get_items_or_404(view_function):
    """
    Decorator that resolves an ``Item`` from ``item_id`` and downcasts
    it to its concrete subclass (JournalPub / Book / ConferenceProceeding
    / Thesis based on ``item_type``). 404s if no Item matches.

    Phase 5 removed the ``download.pdf`` branch: PDFs are no longer
    exposed publicly (copyright restriction), so the only path through
    this decorator is canonical-URL handling for ``view_item``.
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
            return redirect(
                "/".join(["/item", str(item_id), the_item.slug]), permanent=True
            )

        if the_item.item_type == "conferenceproc":
            the_item = ConferenceProceeding.objects.get(id=item_id)
        if the_item.item_type == "thesis":
            the_item = Thesis.objects.get(id=item_id)
        if the_item.item_type == "journalpub":
            the_item = JournalPub.objects.get(id=item_id)
        if the_item.item_type == "book":
            the_item = Book.objects.get(id=item_id)

        return view_function(request, the_item, slug)

    return decorator


def show_items(request, what_view="", extra_info=""):
    """
    Shows a paginated list of items
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
    if what_view == "tag":
        _track_hit(request, "lit-tag-page", hit_slug)
        all_items = Item.objects.all().filter(tags__slug=slugify(extra_info))
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
        page_title = "All entries published in "
        extra_info = "%s" % extra_info
        entry_order = list(all_items)

    elif what_view == "author":
        author = Author.objects.filter(slug=extra_info)
        if len(author) == 0:
            return page_404_error(
                request, 'There are no publications by "%s"' % extra_info
            )

        _track_hit(request, "lit-author-page", hit_slug)
        author_items = Item.objects.all().filter(authors__slug=extra_info)
        page_title = "All entries by author"
        extra_info = ' "%s"' % author[0].full_name
        entry_order = list(author_items)

    elif what_view == "journal":
        journal = Journal.objects.filter(slug=extra_info)
        if len(journal) == 0:
            return page_404_error(
                request, 'There are no publications in "%s"' % extra_info
            )

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
        },
    )


@get_items_or_404
def view_item(request, the_item, slug):
    """
    Show the full details of one item.

    No PDF download path exists (Phase 5 removed it for copyright
    reasons). The detail page surfaces citation, abstract, DOI /
    external link, and tags only.
    """
    logger.debug("Viewing: %s", the_item)

    create_hit(request, the_item.pk)
    return render(
        request,
        "items/item.html",
        {
            "item": the_item,
            "tag_list": the_item.tags.all(),
        },
    )


def __extract_extra__(request, item_id=None):
    """
    Admin-only endpoint that extracts plain text from each Item's PDF
    via pdfplumber and stores it in Item.other_search_text so the
    Postgres-FTS search vector (Phase 3) can index it. Replaces the
    legacy pdfminer chain.
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
