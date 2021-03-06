from django.db import models


class PageHit(models.Model):
    """ Records each hit (page view) of an item: whether the item is a link,
    code snippet or library, tag, person's profile, etc.

    The only requirement is that the item must have an integer primary key.
    """
    ua_string = models.CharField(max_length=255) # browser's user agent
    ip_address = models.GenericIPAddressField()
    datetime = models.DateTimeField(auto_now=True)
    item = models.CharField(max_length=50)
    item_pk = models.IntegerField()
    extra_info = models.CharField(max_length=512, null=True, blank=True)

    def __str__(self):
        return '%s at %s' % (self.item, self.datetime)


    def most_viewed(self, field):
        """ Most viewed in terms of a certain item.
        """
        return PageHit.objects.filter(item=field)\
                            .annotate(score=models.Count('item'))\
                            .order_by('-score')
