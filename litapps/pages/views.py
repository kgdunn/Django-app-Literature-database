from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse
from django.template.loader import get_template
#from haystack.views import SearchView

from litapps.pagehit.views import create_hit
from litapps.utils import get_IP_address

import logging
logger = logging.getLogger('Literature')
logger.debug('Initializing litapps::pages::views.py')

def front_page(request):
    return render_to_response('pages/front-page.html', {},
                              context_instance=RequestContext(request))


def about_page(request):
    return render_to_response('pages/about-page.html', {},
                              context_instance=RequestContext(request))


def page_404_error(request, extra_info=''):
    """ Override Django's 404 handler, because we want to log this also.
    """
    #ip = get_IP_address(request)
    #logger.info('404 from %s for request "%s"; extra info=%s' %\
    #                                      (ip, request.path, str(extra_info)))
    t = get_template('404.html')
    c = RequestContext(request)
    c.update({'extra_info': extra_info})
    html = t.render(c)
    return HttpResponse(html, status=404)


def page_500_error(request):
    """ Override Django's 500 handler, because we want to log this also.
    """
    #ip = get_IP_address(request)
    #logger.error('500 from %s for request "%s"' % (ip, request.path))
    t = get_template('500.html')
    html = t.render(RequestContext(request))
    return HttpResponse(html, status=500)


def search(request):
    """
    Calls Haystack, but allows us to first log the search query
    """
    if request.GET['q'].strip() == '':
        return redirect(front_page)

    # Avoid duplicate logging if search request results in more than 1 page
    if 'page' not in request.GET:
        create_hit(request, 'haystack_search', request.GET['q'])
        logger.info('SEARCH [%s]: %s' % (get_IP_address(request),
                                         request.GET['q']))
    return SearchView().__call__(request)
