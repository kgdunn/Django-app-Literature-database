import re
import unicodedata

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, URLValidator
from django.db import models
from django.db.models.functions import Lower
from django.template.defaultfilters import slugify
from django.urls import reverse

from utils import unique_slugify


def validate_doi_or_url(value):
    """Accept either a full URL or a bare DOI suffix (e.g. ``10.1234/foo``).

    Bare suffixes get prefixed with ``https://doi.org/`` by
    ``Item.save()``. This loosened validator (vs. plain URLField) lets
    admins paste DOIs directly off a publisher's page without manually
    typing the doi.org prefix every time.
    """
    if not value:
        return
    if value.startswith(("http://", "https://")):
        URLValidator()(value)
        return
    # Common DOI shorthands the admin might paste; normalised at save.
    if value.startswith(("doi.org/", "dx.doi.org/", "10.")):
        return
    raise ValidationError("Enter a full URL (https://...) or a DOI starting with '10.'.")


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
        return reverse("lit-show-items", kwargs={"what_view": "author", "extra_info": self.slug})

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

    class Meta:
        # Issue #23: case-insensitive uniqueness on Journal.name.
        # Postgres builds a functional unique index on LOWER(name) so
        # "Analytica Chimica Acta" and "analytica chimica acta" can't
        # coexist. The data merge that runs alongside this constraint
        # lives in migration 0007.
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_journal_name_case_insensitive",
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """
        Create a URL to display all publications from this journal
        """
        return reverse("lit-show-items", kwargs={"what_view": "journal", "extra_info": self.slug})

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
        ("incollection", "Book chapter"),
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
    # CharField (not URLField) so the validator can accept bare DOI
    # suffixes — see validate_doi_or_url above. Item.save() normalises
    # accepted values to a canonical https://doi.org/<suffix> URL so
    # downstream code (full_citation, doi_link_cleaned, the admin
    # list_display column) sees one shape only.
    doi_link = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="DOI link",
        help_text="Full URL or bare DOI (e.g. 10.1234/foo).",
        validators=[validate_doi_or_url],
    )
    web_link = models.URLField(
        blank=True,
        null=True,
    )
    tags = models.ManyToManyField("tagging.Tag")
    abstract = models.TextField(blank=True)
    date_created = models.DateTimeField(editable=False, auto_now=True)

    # PDFs are uploaded by site admins and consumed by the
    # ``__extract_extra__`` admin endpoint, which extracts plain text via
    # pdfplumber into ``other_search_text`` for the Postgres FTS pipeline.
    # By default they are NEVER served to end users (copyright restriction):
    # the only way to expose one publicly is to flip ``pdf_is_public`` on
    # for that specific item (see below). Caddy still 404s direct
    # ``/media/literature/pdf/*`` access in production, so the flag — checked
    # in the ``view_pdf`` Django view — is the single gate that can open a
    # PDF to the public.
    #
    # Issue #82: ``FileExtensionValidator(allowed_extensions=["pdf"])``
    # rejects non-.pdf uploads at the admin form level — pure data-quality
    # since PDFs aren't publicly served. Mismatched extensions used to slip
    # through and only fail later in ``__extract_extra__`` when pdfplumber
    # raised on a non-PDF body.
    pdf_file = models.FileField(
        upload_to=upload_dest,
        max_length=255,
        blank=True,
        null=True,
        verbose_name="PDF file (admin-only unless 'PDF is public' is ticked)",
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )

    # Default-off override that exposes ``pdf_file`` to the public via the
    # ``view_pdf`` view. Leave it unticked (the default) for every
    # copyright-restricted PDF; tick it only for the handful of genuinely
    # public / open-access documents that may be shown to visitors. With the
    # box off, ``view_pdf`` 404s and no PDF link is rendered on the detail
    # page — so the catalogue's default-deny posture is preserved per item.
    pdf_is_public = models.BooleanField(
        default=False,
        verbose_name="PDF is public",
        help_text="Tick to show this item's PDF to visitors. Off by default — leave off for copyright-restricted PDFs.",
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
        2: Smith and Weston
        3: Joyce, Smith and Smythe
        """
        auth_list = self.authors.all().order_by("authorgroup__order")
        authors = []
        for auth in auth_list:
            author = unicodedata.normalize("NFKD", auth.last_name).encode("ascii", "ignore").decode("ascii")
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
        return self._format_authors_html(self.authors.all().order_by("authorgroup__order"))

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
        """Return the canonical detail-page URL for this item.

        Built by appending ``<pk>/<slug>`` to the resolved ``lit-view-item``
        route prefix so the URL matches the ``urls.py`` pattern even though
        the route itself takes only the id+slug pair.
        """
        return reverse("lit-view-item", args=[0]).rstrip("0") + "%d/%s" % (
            self.pk,
            self.slug,
        )

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        unique_slugify(self, self.title[0:255], "slug")
        if self.doi_link:
            self.doi_link = self._normalize_doi_link(self.doi_link)
        super(Item, self).save(*args, **kwargs)

    @staticmethod
    def _normalize_doi_link(value):
        """Coerce admin-pasted DOI shorthands to the canonical
        ``https://doi.org/<suffix>`` URL. See ``validate_doi_or_url``
        for the accepted input shapes."""
        value = value.strip()
        if not value:
            return value
        if value.startswith(("http://", "https://")):
            return value
        if value.startswith(("doi.org/", "dx.doi.org/")):
            return "https://" + value
        if value.startswith("10."):
            return "https://doi.org/" + value
        return value  # the validator already gated this, defensive only


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
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, blank=True, null=True)

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


class InCollection(Item):
    """A chapter within an edited (or authored) book — typically a
    book chapter or contribution in a multi-author volume.

    Multi-table inheritance via the implicit ``item_ptr`` OneToOne to
    ``Item`` (mirrors the JournalPub / Book / ConferenceProceeding /
    Thesis pattern). ``Item.title`` is the chapter title; ``book_title``
    on this subclass is the parent book's title.
    """

    book_title = models.CharField(
        max_length=510,
        help_text="Title of the book containing this chapter.",
    )
    editors = models.ManyToManyField(Author, blank=True)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, blank=True, null=True)
    edition = models.CharField(max_length=100, blank=True, null=True)
    isbn = models.CharField(max_length=20, blank=True, null=True, verbose_name="ISBN")
    page_start = models.CharField(max_length=10, blank=True, null=True)
    page_end = models.CharField(max_length=10, blank=True, null=True)

    class Meta:
        verbose_name = "book chapter"
        verbose_name_plural = "book chapters"

    @property
    def full_editor_listing(self):
        """Hyperlinked editor names — same shape as ``full_author_listing``.
        Reuses ``Item._format_authors_html`` so the byline rendering is
        identical to Book / ConferenceProceeding."""
        return self._format_authors_html(self.editors.all())

    def full_citation(self):
        """Returns details about the book chapter in HTML form.

        Format: ``Author: "Chapter title" in Editors (eds.) "Book Title",
        edition, publisher, pp. X–Y, year.``
        """
        authors = self.full_author_listing
        editors_html = self.full_editor_listing
        in_phrase = '"<i>%s</i>"' % self.book_title
        if editors_html:
            plural = "eds." if self.editors.count() > 1 else "ed."
            in_phrase = "in %s (%s), %s" % (editors_html, plural, in_phrase)
        else:
            in_phrase = "in %s" % in_phrase
        parts = ['"%s"' % self.title, in_phrase]
        if self.edition:
            parts.append(self.edition)
        if self.publisher:
            parts.append(str(self.publisher))
        if self.page_start and self.page_end:
            parts.append("pp. %s–%s" % (self.page_start, self.page_end))
        elif self.page_start:
            parts.append("p. %s" % self.page_start)
        parts.append(str(self.year_as_url))
        body = ", ".join(parts) + "."
        if authors:
            return "%s: %s" % (authors, body)
        return body
