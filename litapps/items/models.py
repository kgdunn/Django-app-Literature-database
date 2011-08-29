from django.db import models
from django.contrib import admin
from django.template.defaultfilters import slugify
from litapps.utils import unique_slugify

class Author(models.Model):
    first_name = models.CharField(max_length=255)
    middle_initials = models.CharField(max_length=31, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=510, editable=False)

    class Meta:
        ordering = ['last_name']

    def __unicode__(self):
        if self.middle_initials:
            return '%s, %s %s' % (self.last_name, self.first_name,
                                  self.middle_initials)
        else:
            return '%s, %s' % (self.last_name, self.first_name)

    @property
    def full_name(self):
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
        unique_slugify(self, self.full_name, 'slug')
        super(Author, self).save(*args, **kwargs)


class AuthorGroup(models.Model):
    """ Ensures the author order is correctly added """
    author = models.ForeignKey(Author)
    item = models.ForeignKey('Item')
    order = models.IntegerField(default=0)


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
    website = models.URLField(verify_exists=False)
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

    authors = models.ManyToManyField(Author, through='AuthorGroup')
    title = models.TextField()
    slug = models.SlugField(max_length=100, editable=False)
    item_type = models.CharField(max_length=20, choices=ITEM_CHOICES)
    year = models.PositiveIntegerField()
    doi_link = models.URLField(blank=True, null=True, verify_exists=False)
    web_link = models.URLField(blank=True, null=True, verify_exists=False)
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

    @property
    def author_list(self):
        """ For display purposes only
        """
        auth_list = self.authors.all().order_by('authorgroup__order')
        if len(auth_list) > 2:
            #return ', '.join([auth.last_name for auth in auth_list])
            return auth_list[0].last_name + ' et al.'
        elif len(auth_list) == 2:
            return ' and '.join([auth.last_name for auth in auth_list])
        else:
            return auth_list[0].last_name


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


