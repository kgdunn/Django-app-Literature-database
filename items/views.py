import logging
import re
import unicodedata

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.defaultfilters import slugify
from django.urls import reverse

from items.models import Author, Book, ConferenceProceeding, Item, Journal, JournalPub, Thesis
from pagehit.views import create_hit
from pages.views import page_404_error
from utils import invalid_IP_address, paginated_queryset

logger = logging.getLogger(__name__)


def get_items_or_404(view_function):
    """
    Decorator for views that ensures the item requested
    actually exist. If not, throws a 404, else, it calls the view function
    with the required inputs.
    """
    def decorator(request, item_id, slug=None):
        """Retrieves the ``Item`` when given the primary key (``item_id``).
        ``slug`` is ignored for now - just used to create good SEO URLs.
        """
        try:
            the_item = Item.objects.all().filter(id=item_id)
        except ObjectDoesNotExist:
            return page_404_error(request, 'You request a non-existant item')

        if len(the_item) == 0:
            return page_404_error(request, 'This item does not exist yet')

        the_item = the_item[0]
        # Is the URL of the form: "..../NN/XXXX"; if so, then XXXX the item
        path_split = request.path.split('/')
        if len(path_split) >= 4 and path_split[3] in ['download.pdf', ]:
            return view_function(request, the_item)

        # Is the URL not the canonical URL for the item? Redirect the user.
        if slug is None or the_item.slug != slug:
            return redirect('/'.join(['/item',
                                      str(item_id),
                                      the_item.slug]),
                            permanent=True)

        if the_item.item_type == 'conferenceproc':
            the_item = ConferenceProceeding.objects.get(id=item_id)
        if the_item.item_type == 'thesis':
            the_item = Thesis.objects.get(id=item_id)
        if the_item.item_type == 'journalpub':
            the_item = JournalPub.objects.get(id=item_id)
        if the_item.item_type == 'book':
            the_item = Book.objects.get(id=item_id)

        return view_function(request, the_item, slug)

    return decorator


def show_items(request, what_view='', extra_info=''):
    """
    Shows a paginated list of items
    """
    what_view = what_view.lower()
    extra_info = extra_info.lower()
    entry_order = []
    page_title = ''
    template_name = 'items/show-entries.html'
    if what_view == 'tag':
        all_items = Item.objects.all().filter(tags__slug=slugify(extra_info))
        page_title = 'All entries tagged'
        extra_info = ': "%s"' % extra_info
        entry_order = list(all_items)

    elif what_view == 'show' and extra_info == 'all-tags':
        page_title = 'All tags'
        template_name = 'items/show-tag-cloud.html'

    elif what_view == 'show' and extra_info == 'all-items':
        all_items = Item.objects.all().order_by('-year')
        page_title = 'All items in our database '
        extra_info = '(reverse publication date order)'
        entry_order = list(all_items)

    elif what_view == 'pub-by-year':
        all_items = Item.objects.all().filter(year=extra_info)
        page_title = 'All entries published in '
        extra_info = '%s' % extra_info
        entry_order = list(all_items)

    elif what_view == 'author':
        author = Author.objects.filter(slug=extra_info)
        if len(author) == 0:
            return page_404_error(request, 'There are no publications by "%s"' % extra_info)

        author_items = Item.objects.all().filter(authors__slug=extra_info)
        page_title = 'All entries by author'
        extra_info = ' "%s"' % author[0].full_name
        entry_order = list(author_items)

    elif what_view == 'journal':
        journal = Journal.objects.filter(slug=extra_info)
        if len(journal) == 0:
            return page_404_error(request, 'There are no publications in "%s"' % extra_info)

        journal_items = JournalPub.objects.all().filter(journal=journal[0])
        page_title = 'All entries in '
        extra_info = ' "%s"' % journal[0].name
        entry_order = list(journal_items)

    entries = paginated_queryset(request, entry_order)
    return render(request, template_name, {
        'entries': entries,
        'page_title': page_title,
        'extra_info': extra_info,
    })


@get_items_or_404
def download_item(request, the_item):
    """
    Return the PDF to the user.

    Phase 5 will harden this further: tighten the URL regex before any DB
    lookup, stream via FileResponse, and revisit the Item.private_pdf /
    invalid_IP_address ACL (which doesn't compose with Cloudflare's edge
    IP rewrite). For Phase 1 this is the legacy behaviour with the Py2
    artefacts removed.
    """
    create_hit(request, the_item.pk, extra_info="download-pdf")
    if not the_item.pdf_file:
        return page_404_error(request, 'This item does not have a PDF file.')

    title = (
        unicodedata.normalize('NFKD', the_item.title)
        .encode('ascii', 'ignore')
        .decode('ascii')
    )
    title = re.sub(r'[^\w\s-]', '', title).strip()
    pdf_name = '%s -- %s.pdf' % (the_item.author_slugs, title)

    if the_item.private_pdf:
        return page_404_error(request, "This item's PDF file is not available.")

    # Only check IPs if we have a valid download link
    if invalid_IP_address(request):
        return page_404_error(request, "This item's PDF file cannot be downloaded.")

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename=%s' % pdf_name
    response.write(the_item.pdf_file.read())
    return response


@get_items_or_404
def view_item(request, the_item, slug):
    """
    Show the full details of one item
    """
    if the_item.pdf_file:
        the_item.download_link = reverse('lit-download-pdf', args=[the_item.pk])
        try:
            the_item.download_size = the_item.pdf_file.size
        except OSError:
            # We couldn't find the file: has been removed from storage?
            the_item.download_link = ''
    else:
        the_item.download_link = ''

    if the_item.private_pdf:
        the_item.download_link = ''

    # Only check IPs if we have a valid download link
    if (the_item.download_link) and invalid_IP_address(request):
        the_item.download_link = ''

    logger.debug('Viewing: %s', the_item)

    create_hit(request, the_item.pk)
    return render(request, 'items/item.html', {
        'item': the_item,
        'tag_list': the_item.tags.all(),
    })


def __extract_extra__(request, item_id=None):
    """
    Admin-only endpoint that extracts plain text from each Item's PDF
    via pdfplumber and stores it in Item.other_search_text so the
    Postgres-FTS search vector (Phase 3) can index it. Replaces the
    legacy pdfminer chain.
    """
    if not request.user.is_authenticated:
        return HttpResponse('Please sign in first')

    import pdfplumber

    if item_id:
        all_items = Item.objects.filter(id=item_id)
    else:
        all_items = Item.objects.all()

    last_title = ''
    for item in all_items:
        # Don't extract if no PDF exists; or if we already have search text.
        if not item.pdf_file or item.other_search_text:
            continue

        last_title = item.title
        try:
            with pdfplumber.open(item.pdf_file.path) as pdf:
                pages = [page.extract_text() or '' for page in pdf.pages]
        except Exception:  # pdfplumber raises a broad set of errors
            logger.warning('FAILED in completely PDF index "%s"', item.title)
            return HttpResponse('FAILED in completely PDF index "%s"' % item.title)

        item.other_search_text = '\n'.join(pages)
        item.save()
        logger.debug('Full PDF index of item "%s"', item.title)

    return HttpResponse('Full PDF indexed for item "%s"' % last_title)
