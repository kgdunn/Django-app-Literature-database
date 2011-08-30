from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.http import HttpResponse
import models

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
            return '404'#page_404_error(request, 'You request a non-existant item')

        if len(the_item) == 0:
            return '404' #page_404_error(request, 'This item does not exist yet')

        the_item = the_item[0]

        # Is the URL of the form: "..../NN/XXXX"; if so, then XXXX the item
        path_split = request.path.split('/')
        #if len(path_split)>3 and path_split[3] in ['download', ]:
            #if path_split[3] == 'download' and len(path_split)>=6:
                #return view_function(request, the_submission, the_revision,
                                     #filename=path_split[5:])
            #else:
                #return view_function(request, the_submission, the_revision)

        # Is the URL not the canonical URL for the item? .... redirect the user
        #else:
        if slug is None or the_item.slug != slug:
            return redirect('/'.join(['/item',
                                      item_id,
                                      the_item.slug]),
                            permanent=True)


        return view_function(request, the_item, slug)

    return decorator



def show_items(request, what_view, extra_info):
    return 'show_items'#render_to_response('pages/front-page.html', {},
           #                   context_instance=RequestContext(request))

def download_item(request, item_id):
    return 'PDF'

@get_items_or_404
def view_item(request, the_item, slug):
    """
    Show the full details of the article
    """

    return render_to_response('items/item.html', {},
                              context_instance=RequestContext(request,
                                    {'item': the_item,
                                     'tag_list': the_item.tags.all(),
                                    }))
