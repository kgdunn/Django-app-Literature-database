from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
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
    #    image = models.ImageField(upload_to='tags/', blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Set the slug from the name on first save; raise loudly on a
        slug collision.

        Issue #83: the legacy implementation silently no-op'd when the
        slug already existed, which produced two surprising outcomes:

        1. ``Tag.objects.create(name="Already taken")`` returned a Tag
           instance that was *never persisted*, so callers thought the
           tag was saved when it wasn't.
        2. Editing an existing tag's ``description`` and re-saving was
           rejected, because the row treated *itself* as a collision
           via ``Tag.objects.filter(slug=slug)``.

        The fix: only check for a collision when this is a new row
        (``self.pk is None``). On the update path, the DB-level
        ``unique=True`` constraint on ``slug`` is the safety net.
        Real collisions raise ``IntegrityError`` instead of silently
        dropping the write.
        """
        new_slug = slugify(self.name)

        # Happens if the name is purely unicode characters slugify can't
        # handle, e.g. an emoji-only tag name.
        if not new_slug:
            raise ValidationError("Tag contains invalid characters")

        if self.pk is None and Tag.objects.filter(slug=new_slug).exists():
            raise IntegrityError("A tag with slug '%s' already exists" % new_slug)

        self.slug = new_slug
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["slug"]
