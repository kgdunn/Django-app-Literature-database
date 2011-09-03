from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.core.exceptions import ObjectDoesNotExist
from django.template.defaultfilters import slugify
from django.core.urlresolvers import reverse
from django.http import HttpResponse

from litapps.pages.views import page_404_error
from litapps.utils import paginated_queryset, invalid_IP_address
from litapps.pagehit.views import create_hit
from templatetags.core_tags import most_viewed

import models

import re
import unicodedata
import logging

logger = logging.getLogger('Literature')
logger.debug('Initializing litapps::items::views.py')

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
            # Use the Submissions manager's ``all()`` function
            the_item = models.Item.objects.all().filter(id=item_id)
        except ObjectDoesNotExist:
            return page_404_error(request, 'You request a non-existant item')

        if len(the_item) == 0:
            return page_404_error(request, 'This item does not exist yet')

        the_item = the_item[0]
        # Is the URL of the form: "..../NN/XXXX"; if so, then XXXX the item
        path_split = request.path.split('/')
        if len(path_split)>=4 and path_split[3] in ['download.pdf', ]:
            return view_function(request, the_item)

        # Is the URL not the canonical URL for the item? .... redirect the user
        #else:
        if slug is None or the_item.slug != slug:
            return redirect('/'.join(['/item',
                                      item_id,
                                      the_item.slug]),
                            permanent=True)


        if the_item.item_type == 'conferenceproc':
            the_item = models.ConferenceProceeding.objects.get(id=item_id)
        if the_item.item_type == 'thesis':
            the_item = models.Thesis.objects.get(id=item_id)
        if the_item.item_type == 'journalpub':
            the_item = models.JournalPub.objects.get(id=item_id)
        if the_item.item_type == 'book':
            the_item = models.Book.objects.get(id=item_id)

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
        all_items = models.Item.objects.all().\
                                        filter(tags__slug=slugify(extra_info))
        page_title = 'All entries tagged'
        extra_info = ': "%s"' % extra_info
        entry_order = list(all_items)

    elif what_view == 'show' and extra_info == 'all-tags':
        page_title = 'All tags'
        template_name = 'items/show-tag-cloud.html'

    elif what_view == 'show' and extra_info == 'all-items':
        all_items = models.Item.objects.all().order_by('-year')
        page_title = 'All items in our database '
        extra_info = '(reverse publication date order)'
        entry_order = list(all_items)

    elif what_view == 'sort' and extra_info == 'most-viewed':
        page_title = 'All references (in order of most viewed)'
        extra_info = ''
        entry_order = most_viewed('item', models.Item.objects.count())

    elif what_view == 'pub-by-year':
        all_items = models.Item.objects.all().filter(year=extra_info)
        page_title = 'All entries published in '
        extra_info = '%s' % extra_info
        entry_order = list(all_items)

    elif what_view == 'author':
        author = models.Author.objects.filter(slug=extra_info)
        if len(author) == 0:
            return page_404_error(request, 'There are no publications by "%s"' % extra_info)

        author_items = models.Item.objects.all().filter(authors__slug=extra_info)
        page_title = 'All entries by author'
        extra_info = ' "%s"' % author[0].full_name
        entry_order = list(author_items)

    elif what_view == 'journal':
        journal = models.Journal.objects.filter(slug=extra_info)
        if len(journal) == 0:
            return page_404_error(request, 'There are no publications in "%s"' % extra_info)

        journal_items = models.JournalPub.objects.all().filter(journal=journal[0])
        page_title = 'All entries in '
        extra_info = ' "%s"' % journal[0].name
        entry_order = list(journal_items)

    #elif what_view == 'show' and extra_info == 'top-authors':
    #    page_title = 'Top authors'
    #    extra_info = ''
    #    #entry_order = top_authors('', 0)

    entries = paginated_queryset(request, entry_order)
    return render_to_response(template_name, {},
                              context_instance=RequestContext(request,
                                                {'entries': entries,
                                                 'page_title': page_title,
                                                 'extra_info': extra_info}))


@get_items_or_404
def download_item(request, the_item):
    """
    Return the PDF to the user
    """
    create_hit(request, the_item.pk, extra_info="download-pdf")
    if the_item.pdf_file:
        title = unicodedata.normalize('NFKD', the_item.title).encode('ascii', 'ignore')
        title = unicode(re.sub('[^\w\s-]', '', title).strip())
        pdf_name = '%s -- %s.pdf' % (the_item.author_slugs, title)
    else:
        return page_404_error(request, 'This item does not have a PDF file.')

    if the_item.private_pdf:
        return page_404_error(request, "This item's PDF file is not available.")

    # Only check IPs if we have a valid download link
    if invalid_IP_address(request):
        return page_404_error(request, "This item's PDF file cannot be downloaded.")

    response = HttpResponse(mimetype="application/pdf")
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

    create_hit(request, the_item.pk)

    return render_to_response('items/item.html', {},
                              context_instance=RequestContext(request,
                                    {'item': the_item,
                                     'tag_list': the_item.tags.all(),
                                    }))


def __extract_extra__(request):
    if not request.user.is_authenticated():
        return HttpResponse('Please sign in first')

    from pdfminer.layout import LAParams
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter, process_pdf
    from pdfminer.pdfdevice import PDFDevice, TagExtractor
    from pdfminer.converter import TextConverter
    from cStringIO import StringIO

    laparams = LAParams()
    outtype = 'text'
    laparams.char_margin = 1.0
    laparams.line_margin = 0.3
    laparams.word_margin = 0.2
    codec = 'utf-8'
    caching = True

    for item in models.Item.objects.all():

        # Don't extract if no PDF; or if we already have search text
        if not item.pdf_file or item.other_search_text:
            continue

        print 'Item: "%s" ... ' % item.title,
        rsrcmgr = PDFResourceManager(caching=caching)
        outfp = StringIO()
        device = TextConverter(rsrcmgr, outfp, codec=codec, laparams=laparams)
        fp = item.pdf_file.file
        try:
            process_pdf(rsrcmgr, device, fp, pagenos=set(), maxpages=0, password='',
                        caching=caching, check_extractable=True)
        except AssertionError:
            print 'FAILED.'
        else:
            print 'done.'
        finally:
            fp.close()
            device.close()
            outfp.seek(0)
            page_text = outfp.read()
            outfp.close()

            #''.join([line[0:-1] for line in r])
            item.other_search_text = page_text
            item.save()



    return HttpResponse('Done. You should rebuild the index again.')

