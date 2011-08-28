from django.db import models
from django.template.defaultfilters import slugify

class Tag(models.Model):
    """
    A tag object: each item can have several tags. All tags must have
    a unique slug name.
    """
    # Name used for URLs and tag blocks
    slug = models.SlugField(unique=True, editable=False)

    # Show this longer name when user hovers their mouse
    name = models.CharField(max_length=50)

    # We may decide to have a page for each tag, where we show these
    # descriptions
    description = models.CharField(max_length=255, blank=True, null=True)
    # and perhaps an image
    image = models.ImageField(upload_to='tags/', blank=True)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        """ Slug is a primary key: don't save a new tag if one already exists
        with the identical slug.
        """
        slug = slugify(self.name)

        # happens if the slug is totally unicode characters
        if len(slug) == 0:
            raise ValidationError('Tag contains invalid characters')

        if Tag.objects.filter(slug=slug):
            return
        else:
            # Call the "real" save() method.
            self.slug = slug
            super(Tag, self).save(*args, **kwargs)
