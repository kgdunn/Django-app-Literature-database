from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse

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