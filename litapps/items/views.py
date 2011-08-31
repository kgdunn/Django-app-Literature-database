from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.core.exceptions import ObjectDoesNotExist
from django.template.defaultfilters import slugify
from django.core.urlresolvers import reverse
from django.http import HttpResponse

from litapps.pages.views import page_404_error
from litapps.utils import paginated_queryset, invalid_IP_address

import models

import re
import unicodedata

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
    elif what_view == 'show' and extra_info == 'author-list':
        pass
    elif what_view == 'show' and extra_info == 'top-authors':
        page_title = 'Top authors'
        extra_info = ''
        #entry_order = top_authors('', 0)

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
    if the_item.pdf_file:
        title = unicodedata.normalize('NFKD', the_item.title).encode('ascii', 'ignore')
        title = unicode(re.sub('[^\w\s-]', '', title).strip())
        pdf_name = '%s--%s.pdf' % (the_item.author_slugs, title)
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
        the_item.downlad_size = the_item.pdf_file.size
    else:
        the_item.download_link = ''

    if the_item.private_pdf:
        the_item.download_link = ''

    # Only check IPs if we have a valid download link
    if (the_item.download_link) and invalid_IP_address(request):
        the_item.download_link = ''

    return render_to_response('items/item.html', {},
                              context_instance=RequestContext(request,
                                    {'item': the_item,
                                     'tag_list': the_item.tags.all(),
                                    }))
