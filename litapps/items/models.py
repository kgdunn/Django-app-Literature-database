from django.db import models
from django.contrib import admin
from django.template.defaultfilters import slugify
from litapps.utils import unique_slugify

class Author(models.Model):
    first_name = models.CharField(max_length=255)
    middle_initials = models.CharField(max_length=31, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=510, editable=False)

    def __unicode__(self):
        if self.middle_initials:
            return '%s %s %s' % (self.first_name, self.middle_initials,
                                 self.last_name)
        else:
            return '%s %s' % (self.first_name, self.last_name)

    def save(self, *args, **kwargs):
        """
        http://docs.djangoproject.com/en/dev/topics/db/models/
                                          overriding-predefined-model-methods
        """
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.slug = slugify(str(self))

        super(Author, self).save(*args, **kwargs)


class School(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, editable=False)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        http://docs.djangoproject.com/en/dev/topics/db/models/
                                          overriding-predefined-model-methods
        """
        self.name = self.name.strip()
        self.slug = slugify(self.name)

        super(School, self).save(*args, **kwargs)


class Journal(models.Model):
    name = models.CharField(max_length=510)
    website = models.URLField()
    slug = models.SlugField(max_length=510, editable=False)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        http://docs.djangoproject.com/en/dev/topics/db/models/
                                          overriding-predefined-model-methods
        """
        self.name = self.name.strip()
        self.slug = slugify(str(self))
        super(Journal, self).save(*args, **kwargs)


class Publisher(models.Model):
    name = models.CharField(max_length=510)
    slug = models.SlugField(max_length=510, editable=False)

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        http://docs.djangoproject.com/en/dev/topics/db/models/
                                          overriding-predefined-model-methods
        """
        self.name = self.name.strip()
        self.slug = slugify(str(self))
        super(Publisher, self).save(*args, **kwargs)


class Item(models.Model):
    ITEM_CHOICES = (
        ('thesis',         'Thesis'),
        ('journalpub',     'Journal publication'),
        ('book',           'Book'),
        ('conferenceproc', 'Conference proceeding'),
    )
    def upload_dest(instance, filename):
        """ ``instance.slug`` has already been defined at this point (from
        self.save()), so it can be safely used.
        """
        return 'pdf/%s/%s.pdf' % (instance.slug[0], instance.slug)

    authors = models.ManyToManyField(Author)
    title = models.TextField()
    slug = models.SlugField(max_length=100, editable=False)
    item_type = models.CharField(max_length=20, choices=ITEM_CHOICES)
    year = models.PositiveIntegerField()
    doi_link = models.URLField(blank=True, null=True)
    web_link = models.URLField(blank=True, null=True)
    tags = models.ManyToManyField('tagging.Tag')
    abstract = models.TextField(blank=True)
    date_created = models.DateTimeField(editable=False, auto_now=True)

    pdf_file = models.FileField(upload_to=upload_dest, max_length=255,
                                blank=True, null=True)

    def __unicode__(self):
        if self.doi_link:
            return '%s (%s) [doi:%s]' % (self.title, str(self.year),
                                         self.doi_link)
        else:
            return '%s (%s)' % (self.title, str(self.year))

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        unique_slugify(self, self.title[0:100], 'slug')
        super(Item, self).save(*args, **kwargs)


class JournalPub(Item):
    journal = models.ForeignKey(Journal)
    volume = models.CharField(max_length=100, blank=True, null=True)
    page_start = models.CharField(max_length=10, blank=True, null=True)
    page_end = models.CharField(max_length=10, blank=True, null=True)

    def __unicode__(self):
        return '%s (%s) [doi:%s]' % (self.title, str(self.year),
                                     self.doi_link)

    class Meta:
        verbose_name_plural = "journal publications"


class Book(Item):
    publisher = models.ForeignKey(Publisher)
    editors = models.ManyToManyField(Author, blank=True, null=True)
    volume = models.CharField(max_length=100, blank=True, null=True)
    series = models.CharField(max_length=100, blank=True, null=True)
    edition = models.CharField(max_length=100, blank=True, null=True)
    isbn = models.CharField(max_length=20, blank=True, null=True)


class ConferenceProceeding(Item):
    editors = models.ManyToManyField(Author, blank=True, null=True)
    conference_name = models.CharField(max_length=255, blank=True, null=True)
    page_start = models.CharField(max_length=10, blank=True, null=True)
    page_end = models.CharField(max_length=10, blank=True, null=True)
    organization = models.CharField(blank=True, null=True, max_length=200)
    location = models.CharField(blank=True, null=True, max_length=200)
    publisher = models.ForeignKey(Publisher, blank=True, null=True)

    class Meta:
        verbose_name_plural = "conference proceedings"


class Thesis(Item):
    school = models.ForeignKey(School)
    supervisors = models.ManyToManyField(Author, blank=True, null=True)

    class Meta:
        verbose_name_plural = "theses"


