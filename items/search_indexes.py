from haystack import indexes
from .models import Item

# SearchIndex object for each revision in the database

class ItemIndex(indexes.SearchIndex, indexes.Indexable):

    # The main field to search in:
    # see ``templates/search/indexes/items/item_text.txt``
    text = indexes.CharField(document=True, use_template=True)

    # Include the tags as a search fields
    tags = indexes.CharField()

    def get_model(self):
        return Item

    def index_queryset(self, using=None):
        return self.get_model().objects.all()

