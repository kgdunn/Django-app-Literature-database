from django.db import models
from django.contrib import admin
from django.core.urlresolvers import reverse
from django.template.defaultfilters import slugify
from litapps.utils import unique_slugify

# Standard library imports
import re
import unicodedata

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
            return u'%s %s %s' % (self.first_name, self.middle_initials,
                                   self.last_name)
        else:
            return u'%s %s' % (self.first_name, self.last_name)


    @property
    def full_name_hyperlinked(self):
        if self.middle_initials:
            return u'%s %s %s' % (self.first_name, self.middle_initials,
                                   self.last_name)
        else:
            return u'%s %s' % (self.first_name, self.last_name)


    def get_absolute_url(self):
        """ Create a URL to display all publications by this author
        """
        return reverse('lit-show-items', kwargs={'what_view': 'author',
                                                 'extra_info': self.slug})


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


    def get_absolute_url(self):
        """
        Create a URL to display all publications from this journal
        """
        return reverse('lit-show-items', kwargs={'what_view': 'journal',
                                                 'extra_info': self.slug})

    @property
    def as_url(self):
        return '<a href="%s">%s</a>' % (self.get_absolute_url(), self.name)


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
        return 'literature/pdf/%s/%s.pdf' % (instance.slug[0], instance.slug)

    authors = models.ManyToManyField(Author, through='AuthorGroup')
    title = models.TextField()
    slug = models.SlugField(max_length=255, editable=False)
    item_type = models.CharField(max_length=20, choices=ITEM_CHOICES)
    year = models.PositiveIntegerField()
    doi_link = models.URLField(blank=True, null=True, verify_exists=False,
                               verbose_name='DOI link')
    web_link = models.URLField(blank=True, null=True, verify_exists=False)
    tags = models.ManyToManyField('tagging.Tag')
    abstract = models.TextField(blank=True)
    show_abstract = models.BooleanField(default=False)
    date_created = models.DateTimeField(editable=False, auto_now=True)

    pdf_file = models.FileField(upload_to=upload_dest, max_length=255,
                                blank=True, null=True, verbose_name='PDF file')

    # This PDF should never be shown because it contains personal notes or is
    # not authorized for distributions
    private_pdf = models.BooleanField(default=False,
                                      verbose_name='Private PDF')

    # If ``private_pdf`` is False and this field is True, and there actually
    # exists a PDF, then show the PDF available for download. Usually set
    # True for theses.
    #can_show_pdf = models.BooleanField(default=False,
    #                                   verbose_name='Can show PDF')

    # Contains unstructured text (auto-extracted from PDF, cut/paste, whatever)
    # to improve the user's search
    other_search_text = models.TextField(null=True, blank=True)

    def __unicode__(self):
        if self.doi_link:
            return '%s (%s) [doi:%s]' % (self.title, str(self.year),
                                         self.doi_link)
        else:
            return '%s (%s)' % (self.title, str(self.year))


    @property
    def has_extra(self):
        return bool(self.other_search_text)


    @property
    def year_as_url(self):
        return '<a href="%s">%s</a>' % (reverse('lit-show-items',
                                                kwargs={'what_view': 'pub-by-year',
                                                 'extra_info': self.year}),
                                        self.year)

    @property
    def external_link_text(self):
        """ Text to display for the external link """
        if self.doi_link:
            return 'DOI'
        elif self.web_link:
            return 'More info'
        else:
            return ''


    @property
    def external_link(self):
        """ Hyperlink to use for the external link """
        if self.doi_link:
            return self.doi_link
        elif self.web_link:
            return self.web_link
        else:
            return None


    @property
    def author_list(self):
        """
        1: Duncan
        2: Smith and Weston
        3: Joyce et al.
        """
        auth_list = self.authors.all().order_by('authorgroup__order')
        if len(auth_list) > 2:
            return auth_list[0].last_name + ' <i>et al</i>.'
        elif len(auth_list) == 2:
            return ' and '.join([auth.last_name for auth in auth_list])
        else:
            return auth_list[0].last_name
    #author_list.allow_tags = True


    @property
    def author_slugs(self):
        """
        Used to create the PDF file name. Doesn't matter if there are spaces
        in the last name (i.e. it is not a strict slug), but it does ensure
        the last names only contain normalized unicode characters.

        1: Duncan
        2: Smith-and-Weston
        3: Joyce-Smith-Smythe
        """
        auth_list = self.authors.all().order_by('authorgroup__order')
        authors = []
        for auth in auth_list:
            author = unicodedata.normalize('NFKD', auth.last_name).encode(\
                                                              'ascii', 'ignore')
            author = unicode(re.sub('[^\w\s-]', '', author).strip())
            authors.append(author)

        if len(auth_list) >= 3:
            out = ', '.join([auth for auth in authors[0:-1]])
            out += ' and ' + authors[-1]
            return out
        elif len(auth_list) == 2:
            return ' and '.join(authors)
        else:
            return authors[0]


    @property
    def author_list_all_lastnames(self):
        """
        Provides the hyperlinked author last names in full

        1: Duncan
        2: Smith and Weston
        3: Joyce, Smith and Smythe
        """
        auth_list = list(self.authors.all().order_by('authorgroup__order'))
        def urlize(author):
            return '<a href="%s">%s</a>' % (author.get_absolute_url(),
                                            author.last_name)

        if len(auth_list) >= 3:
            out = ', '.join([urlize(auth) for auth in auth_list[0:-1]])
            out += ' and ' + urlize(auth_list[-1])
        if len(auth_list) == 2:
            out = ' and '.join([urlize(auth) for auth in auth_list])
        if len(auth_list) == 1:
            out = urlize(auth_list[0])
        return out


    @property
    def full_author_listing(self):
        """
        Provides the hyperlinked author names in full

        1: Duncan
        2: John R. Smith and P. Q. Weston
        3: R. W. Joyce, P. J. Smith and T. Y. Smythe
        """
        auth_list = list(self.authors.all().order_by('authorgroup__order'))
        def urlize(author):
            return '<a href="%s">%s</a>' % (author.get_absolute_url(),
                                            author.full_name)

        if len(auth_list) >= 3:
            out = ', '.join([urlize(auth) for auth in auth_list[0:-1]])
            out += ' and ' + urlize(auth_list[-1])
        if len(auth_list) == 2:
            out = ' and '.join([urlize(auth) for auth in auth_list])
        if len(auth_list) == 1:
            out = urlize(auth_list[0])
        return out


    @property
    def doi_link_cleaned(self):
        return self.doi_link.lstrip('http://dx.doi.org/')


    @property
    def previous_item(self):
        n = 1
        item = Item.objects.all().filter(pk=self.pk-n)
        if len(item):
            return item[0].get_absolute_url()
        else:
            return None


    @property
    def next_item(self):
        n = 1
        item = Item.objects.all().filter(pk=self.pk+n)
        if len(item):
            return item[0].get_absolute_url()
        else:
            return None


    def get_absolute_url(self):
        """ I can't seem to find a way to use the "reverse" or "permalink"
        functions to create this URL: do it manually, to match ``urls.py``
        """
        return reverse('lit-view-item', args=[0]).rstrip('0') + \
                '%d/%s' % (self.pk, self.slug)


    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        unique_slugify(self, self.title[0:255], 'slug')
        super(Item, self).save(*args, **kwargs)


class JournalPub(Item):
    journal = models.ForeignKey(Journal)
    volume = models.CharField(max_length=100, blank=True, null=True)
    page_start = models.CharField(max_length=10, blank=True, null=True)
    page_end = models.CharField(max_length=10, blank=True, null=True)

    def __unicode__(self):
        return '%s (%s) [doi:%s]' % (self.title, str(self.year),
                                     self.doi_link)


    def full_citation(self):
        """
        Returns details about the journal publication in HTML form
        """
        return u'%s: "%s", <i>%s</i>, <b>%s</b>, %s-%s, %s.' %\
                                           (self.author_list,
                                            self.title,
                                            self.journal.as_url,
                                            self.volume,
                                            self.page_start,
                                            self.page_end,
                                            self.year_as_url)


    class Meta:
        verbose_name_plural = "journal publications"


class Book(Item):
    publisher = models.ForeignKey(Publisher)
    editors = models.ManyToManyField(Author, blank=True, null=True)
    volume = models.CharField(max_length=100, blank=True, null=True)
    series = models.CharField(max_length=100, blank=True, null=True)
    edition = models.CharField(max_length=100, blank=True, null=True)
    isbn = models.CharField(max_length=20, blank=True, null=True,
                            verbose_name='ISBN')

    def full_citation(self):
        """
        Returns details about the book in HTML form
        """
        edition = self.edition.lower().rstrip('edition')
        if self.edition:
            return '%s: "<i>%s</i>", %s, %s, %s.' %  (self.full_author_listing,
                                                       self.title,
                                                       edition,
                                                       self.publisher,
                                                       self.year_as_url)
        return '%s: "<i>%s</i>", %s, %s.' %  (self.author_list,
                                               self.title,
                                               self.publisher,
                                               self.year_as_url)


class ConferenceProceeding(Item):
    editors = models.ManyToManyField(Author, blank=True, null=True)
    conference_name = models.CharField(max_length=255, blank=True, null=True)
    page_start = models.CharField(max_length=10, blank=True, null=True)
    page_end = models.CharField(max_length=10, blank=True, null=True)
    organization = models.CharField(blank=True, null=True, max_length=200)
    location = models.CharField(blank=True, null=True, max_length=200)
    publisher = models.ForeignKey(Publisher, blank=True, null=True)

    def full_citation(self):
        """
        Returns details about the conference in HTML form
        """
        first =  '%s: "<i>%s</i>", '%  (self.author_list, self.title)
        rest = (item for item in [self.conference_name, self.organization,
                                  self.location, self.publisher] if item)
        rest = ', '.join(rest)

        final = ', %s.' % self.year
        if self.page_start and self.page_end:
            final = ', %s-%s, %s.' % (self.page_start, self.page_end,
                                      self.year)
        elif self.page_start:
            final = ', %s, %s.' % (self.page_start, self.year)

        return first + rest + final

    class Meta:
        verbose_name_plural = "conference proceedings"


class Thesis(Item):
    THESIS_CHOICES = (
        ('masters', 'Masters thesis'),
        ('phd',     'Ph.D thesis'),
    )
    thesis_type = models.CharField(max_length=50, choices=THESIS_CHOICES)
    school = models.ForeignKey(School)
    supervisors = models.ManyToManyField(Author, blank=True, null=True)

    def full_citation(self):
        """
        Returns details about the thesis in HTML form
        """
        thesis_type = ''
        for option_key, option_value in self.THESIS_CHOICES:
            if self.thesis_type == option_key:
                    thesis_type = option_value

        return '%s: "<i>%s</i>", %s, %s, %s.' %  (self.author_list,
                                                  self.title,
                                                  thesis_type,
                                                  self.school,
                                                  self.year_as_url)

    class Meta:
        verbose_name_plural = "theses"


