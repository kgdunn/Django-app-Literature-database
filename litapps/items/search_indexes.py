from haystack import indexes, site
from models import Item

# SearchIndex object for each revision in the database

class ItemIndex(indexes.RealTimeSearchIndex):

    # The main field to search in: see
    # ``deploy/templates/search/indexes/items/item_text.txt``
    text = indexes.CharField(document=True, use_template=True)#model_attr='description')

    # Code submissions: all search the code
    #item_code = indexes.CharField(model_attr='item_code', default='')

    # For link-type submissions: perhaps the link contains the search term
    #item_url = indexes.CharField(model_attr='item_url', default='')

    # Include the tags as a search fields
    tags = indexes.CharField()

    def get_model(self):
        return Item

    #def index_queryset(self):
    #    return self.get_model().objects.all()

    def prepare(self, object):
        """ See http://docs.haystacksearch.org/dev/searchindex_api.html
        """
        self.prepared_data = super(ItemIndex, self).prepare(object)
        self.prepared_data['tags'] = ' '.join([tag.name for tag in object.tags.all()])

        return self.prepared_data

site.register(Item, ItemIndex)