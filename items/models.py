import re
import unicodedata

from django.db import models
from django.template.defaultfilters import slugify
from django.urls import reverse

from utils import unique_slugify


# Custom manager for the items
class LatestItemManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().order_by("-date_created")

    def get_latest(self, n=5):
        return self.get_queryset()[0:n]


class Author(models.Model):
    first_name = models.CharField(max_length=255)
    middle_initials = models.CharField(max_length=31, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=510, editable=False)

    class Meta:
        ordering = ["last_name"]

    def __str__(self):
        if self.middle_initials:
            return "%s, %s %s" % (self.last_name, self.first_name, self.middle_initials)
        else:
            return "%s, %s" % (self.last_name, self.first_name)

    @property
    def full_name(self):
        if self.middle_initials:
            return "%s %s %s" % (self.first_name, self.middle_initials, self.last_name)
        else:
            return "%s %s" % (self.first_name, self.last_name)

    @property
    def full_name_hyperlinked(self):
        if self.middle_initials:
            return "%s %s %s" % (self.first_name, self.middle_initials, self.last_name)
        else:
            return "%s %s" % (self.first_name, self.last_name)

    def get_absolute_url(self):
        """Create a URL to display all publications by this author"""
        return reverse(
            "lit-show-items", kwargs={"what_view": "author", "extra_info": self.slug}
        )

    def save(self, *args, **kwargs):
        """
        http://docs.djangoproject.com/en/dev/topics/db/models/
                                          overriding-predefined-model-methods
        """
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        unique_slugify(self, self.full_name, "slug")
        super(Author, self).save(*args, **kwargs)


class AuthorGroup(models.Model):
    """Ensures the author order is correctly added"""

    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    item = models.ForeignKey("Item", on_delete=models.CASCADE)
    order = models.IntegerField(default=0)


class School(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, editable=False)

    def __str__(self):
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

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """
        Create a URL to display all publications from this journal
        """
        return reverse(
            "lit-show-items", kwargs={"what_view": "journal", "extra_info": self.slug}
        )

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

    def __str__(self):
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

    objects = models.Manager()  # The default manager: 'Item.objects.all()'
    latest_items = LatestItemManager()  # 'Item.latest_items.all()'

    ITEM_CHOICES = (
        ("thesis", "Thesis"),
        ("journalpub", "Journal publication"),
        ("book", "Book"),
        ("conferenceproc", "Conference proceeding"),
    )

    def upload_dest(instance, filename):
        """``instance.slug`` has already been defined at this point (from
        self.save()), so it can be safely used.
        """
        return "literature/pdf/%s/%s.pdf" % (instance.slug[0], instance.slug)

    authors = models.ManyToManyField(Author, through="AuthorGroup")
    title = models.TextField()
    slug = models.SlugField(max_length=255, editable=False)
    item_type = models.CharField(max_length=20, choices=ITEM_CHOICES)
    year = models.PositiveIntegerField()
    doi_link = models.URLField(blank=True, null=True, verbose_name="DOI link")
    web_link = models.URLField(
        blank=True,
        null=True,
    )
    tags = models.ManyToManyField("tagging.Tag")
    abstract = models.TextField(blank=True)
    show_abstract = models.BooleanField(default=False)
    date_created = models.DateTimeField(editable=False, auto_now=True)

    # PDFs are uploaded by site admins and consumed only by the
    # ``__extract_extra__`` admin endpoint, which extracts plain text via
    # pdfplumber into ``other_search_text`` for the Postgres FTS pipeline.
    # They are NEVER served to end users (copyright restriction) — the
    # public ``download_item`` view was removed in Phase 5. Caddy's
    # ``/media/literature/pdf/*`` path is excluded from the static
    # file_server in production for the same reason.
    pdf_file = models.FileField(
        upload_to=upload_dest,
        max_length=255,
        blank=True,
        null=True,
        verbose_name="PDF file (admin-only; not exposed for download)",
    )

    # Contains unstructured text (auto-extracted from PDF, cut/paste, whatever)
    # to improve the user's search
    other_search_text = models.TextField(null=True, blank=True)

    def __str__(self):
        if self.doi_link:
            return "%s (%s) [doi:%s]" % (self.title, str(self.year), self.doi_link)
        else:
            return "%s (%s)" % (self.title, str(self.year))

    @property
    def has_extra(self):
        return bool(self.other_search_text)

    @property
    def year_as_url(self):
        return '<a href="%s">%s</a>' % (
            reverse(
                "lit-show-items",
                kwargs={"what_view": "pub-by-year", "extra_info": self.year},
            ),
            self.year,
        )

    @property
    def external_link_text(self):
        """Text to display for the external link"""
        if self.doi_link:
            return "DOI"
        elif self.web_link:
            return "More info"
        else:
            return ""

    @property
    def external_link(self):
        """Hyperlink to use for the external link"""
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
        auth_list = self.authors.all().order_by("authorgroup__order")
        if len(auth_list) > 2:
            return auth_list[0].last_name + " <i>et al</i>."
        if len(auth_list) == 2:
            return " and ".join([auth.last_name for auth in auth_list])
        if len(auth_list) == 1:
            return auth_list[0].last_name
        return ""

    # author_list.allow_tags = True

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
        auth_list = self.authors.all().order_by("authorgroup__order")
        authors = []
        for auth in auth_list:
            author = (
                unicodedata.normalize("NFKD", auth.last_name)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            author = re.sub(r"[^\w\s-]", "", author).strip()
            authors.append(author)

        if len(auth_list) >= 3:
            out = ", ".join([auth for auth in authors[0:-1]])
            out += " and " + authors[-1]
            return out
        elif len(auth_list) == 2:
            return " and ".join(authors)
        elif len(auth_list) == 1:
            return authors[0]
        return ""

    @property
    def author_list_all_lastnames(self):
        """
        Provides the hyperlinked author last names in full

        1: Duncan
        2: Smith and Weston
        3: Joyce, Smith and Smythe
        """
        auth_list = list(self.authors.all().order_by("authorgroup__order"))

        def urlize(author):
            return '<a href="%s">%s</a>' % (author.get_absolute_url(), author.last_name)

        out = ""
        if len(auth_list) >= 3:
            out = ", ".join([urlize(auth) for auth in auth_list[0:-1]])
            out += " and " + urlize(auth_list[-1])
        if len(auth_list) == 2:
            out = " and ".join([urlize(auth) for auth in auth_list])
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
        return self._format_authors_html(
            self.authors.all().order_by("authorgroup__order")
        )

    @staticmethod
    def _format_authors_html(authors):
        """English-list-join an iterable of Author objects as hyperlinked
        full names. Used for both author and editor bylines so the rendering
        stays identical and we don't drift if one shape gets tweaked.

        0  → ""
        1  → <a>X</a>
        2  → <a>X</a> and <a>Y</a>
        3+ → <a>X</a>, <a>Y</a> and <a>Z</a>
        """
        items = list(authors)
        if not items:
            return ""

        def urlize(a):
            return '<a href="%s">%s</a>' % (a.get_absolute_url(), a.full_name)

        if len(items) == 1:
            return urlize(items[0])
        if len(items) == 2:
            return " and ".join(urlize(a) for a in items)
        return ", ".join(urlize(a) for a in items[:-1]) + " and " + urlize(items[-1])

    @property
    def doi_link_cleaned(self):
        return (
            self.doi_link.removeprefix("https://dx.doi.org/")
            .removeprefix("http://dx.doi.org/")
            .removeprefix("https://doi.org/")
            .removeprefix("http://doi.org/")
        )

    @property
    def previous_item(self):
        n = 1
        item = Item.objects.all().filter(pk=self.pk - n)
        if len(item):
            return item[0].get_absolute_url()
        else:
            return None

    @property
    def next_item(self):
        n = 1
        item = Item.objects.all().filter(pk=self.pk + n)
        if len(item):
            return item[0].get_absolute_url()
        else:
            return None

    def get_absolute_url(self):
        """I can't seem to find a way to use the "reverse" or "permalink"
        functions to create this URL: do it manually, to match ``urls.py``
        """
        return reverse("lit-view-item", args=[0]).rstrip("0") + "%d/%s" % (
            self.pk,
            self.slug,
        )

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        unique_slugify(self, self.title[0:255], "slug")
        super(Item, self).save(*args, **kwargs)


class JournalPub(Item):
    journal = models.ForeignKey(Journal, on_delete=models.CASCADE)
    volume = models.CharField(max_length=100, blank=True, null=True)
    page_start = models.CharField(max_length=10, blank=True, null=True)
    page_end = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return "%s (%s) [doi:%s]" % (self.title, str(self.year), self.doi_link)

    def full_citation(self):
        """
        Returns details about the journal publication in HTML form
        """
        return '%s: "%s", <i>%s</i>, <b>%s</b>, %s-%s, %s.' % (
            self.author_list,
            self.title,
            self.journal.as_url,
            self.volume,
            self.page_start,
            self.page_end,
            self.year_as_url,
        )

    class Meta:
        verbose_name_plural = "journal publications"


class Book(Item):
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    editors = models.ManyToManyField(Author, blank=True)
    volume = models.CharField(max_length=100, blank=True, null=True)
    series = models.CharField(max_length=100, blank=True, null=True)
    edition = models.CharField(max_length=100, blank=True, null=True)
    isbn = models.CharField(max_length=20, blank=True, null=True, verbose_name="ISBN")

    @property
    def full_editor_listing(self):
        """Hyperlinked editor names, English-list-joined. Same shape as
        ``full_author_listing`` so the byline stays uniform between authored
        and edited volumes."""
        return self._format_authors_html(self.editors.all())

    def full_citation(self):
        """Returns details about the book in HTML form."""
        byline = self._book_byline()
        parts = ['"<i>%s</i>"' % self.title]
        if self.edition:
            parts.append(self.edition)
        parts.append(str(self.publisher))
        parts.append(str(self.year_as_url))
        body = ", ".join(parts) + "."
        if byline:
            return "%s: %s" % (byline, body)
        return body

    def _book_byline(self):
        """Compose the leading byline for ``full_citation``. Authors come
        first; if editors are also present (e.g. an authored monograph in an
        edited series) they're appended with the ``(ed.)`` / ``(eds.)``
        suffix. An editors-only volume renders as "<editors> (eds.):"."""
        authors_html = self.full_author_listing
        editors_html = self.full_editor_listing
        if not editors_html:
            return authors_html
        suffix = "eds." if self.editors.count() > 1 else "ed."
        if authors_html:
            return "%s; %s (%s)" % (authors_html, editors_html, suffix)
        return "%s (%s)" % (editors_html, suffix)


class ConferenceProceeding(Item):
    editors = models.ManyToManyField(Author, blank=True)
    conference_name = models.CharField(max_length=255, blank=True, null=True)
    page_start = models.CharField(max_length=10, blank=True, null=True)
    page_end = models.CharField(max_length=10, blank=True, null=True)
    organization = models.CharField(blank=True, null=True, max_length=200)
    location = models.CharField(blank=True, null=True, max_length=200)
    publisher = models.ForeignKey(
        Publisher, on_delete=models.CASCADE, blank=True, null=True
    )

    @property
    def full_editor_listing(self):
        """Hyperlinked editor names — same shape as ``full_author_listing``."""
        return self._format_authors_html(self.editors.all())

    def full_citation(self):
        """
        Returns details about the conference in HTML form
        """
        first = '%s: "<i>%s</i>", ' % (self.author_list, self.title)
        rest = (
            item
            for item in [
                self.conference_name,
                self.organization,
                self.location,
                self.publisher,
            ]
            if item
        )
        rest = ", ".join(rest)

        final = ", %s." % self.year
        if self.page_start and self.page_end:
            final = ", %s-%s, %s." % (self.page_start, self.page_end, self.year)
        elif self.page_start:
            final = ", %s, %s." % (self.page_start, self.year)

        return first + rest + final

    class Meta:
        verbose_name_plural = "conference proceedings"


class Thesis(Item):
    THESIS_CHOICES = (
        ("masters", "Masters thesis"),
        ("phd", "Ph.D thesis"),
    )
    thesis_type = models.CharField(max_length=50, choices=THESIS_CHOICES)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    supervisors = models.ManyToManyField(Author, blank=True)

    def full_citation(self):
        """
        Returns details about the thesis in HTML form
        """
        thesis_type = ""
        for option_key, option_value in self.THESIS_CHOICES:
            if self.thesis_type == option_key:
                thesis_type = option_value

        return '%s: "<i>%s</i>", %s, %s, %s.' % (
            self.author_list,
            self.title,
            thesis_type,
            self.school,
            self.year_as_url,
        )

    class Meta:
        verbose_name_plural = "theses"
