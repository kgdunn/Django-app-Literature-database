"""Tests for the items domain layer (models + properties)."""

import pytest
from django.db import IntegrityError

from items.models import Author


@pytest.mark.django_db
class TestAuthorFullName:
    def test_full_name_without_middle_initials(self):
        a = Author.objects.create(first_name="Albert", last_name="Einstein")
        assert a.full_name == "Albert Einstein"
        assert str(a) == "Einstein, Albert"

    def test_full_name_with_middle_initials(self):
        a = Author.objects.create(
            first_name="John", middle_initials="R.", last_name="Smith"
        )
        assert a.full_name == "John R. Smith"
        assert str(a) == "Smith, John R."


@pytest.mark.django_db
class TestAuthorSlugs:
    def test_one_author(self, journalpub_factory, author):
        item = journalpub_factory(authors=[author])
        assert item.author_slugs == "Einstein"

    def test_two_authors(self, journalpub_factory, two_authors):
        item = journalpub_factory(authors=two_authors)
        # First two: "X and Y"
        assert item.author_slugs == "Einstein and Curie"

    def test_three_authors(self, journalpub_factory, three_authors):
        item = journalpub_factory(authors=three_authors)
        # Three+: "A, B and C"
        assert item.author_slugs == "Joyce, Smith and Smythe"

    def test_unicode_author(self, journalpub_factory, db):
        """`Schroedinger` (with NFKD-normalised umlaut) should slug to ASCII."""
        a = Author.objects.create(first_name="Erwin", last_name="Schrödinger")
        item = journalpub_factory(authors=[a])
        assert item.author_slugs == "Schrodinger"

    def test_no_authors(self, journalpub_factory):
        # Regression for issue #35: legacy code raised IndexError on the
        # `return authors[0]` fall-through when an item had no authors.
        item = journalpub_factory(authors=None)
        assert item.author_slugs == ""


@pytest.mark.django_db
class TestAuthorList:
    """Lastname-only join (used by JournalPub / Book / Conference / Thesis
    full_citation). Exercises the same 0/1/2/3+ shape as author_slugs."""

    def test_no_authors(self, journalpub_factory):
        # Mirror of issue #35 in author_list — same legacy
        # `return auth_list[0].last_name` fall-through.
        item = journalpub_factory(authors=None)
        assert item.author_list == ""

    def test_one_author(self, journalpub_factory, author):
        item = journalpub_factory(authors=[author])
        assert item.author_list == "Einstein"

    def test_two_authors(self, journalpub_factory, two_authors):
        item = journalpub_factory(authors=two_authors)
        assert item.author_list == "Einstein and Curie"

    def test_three_authors_uses_et_al(self, journalpub_factory, three_authors):
        item = journalpub_factory(authors=three_authors)
        assert item.author_list == "Joyce <i>et al</i>."


@pytest.mark.django_db
class TestFullAuthorListing:
    """Hyperlinked full-name byline. Shared with full_editor_listing."""

    def test_no_authors(self, journalpub_factory):
        item = journalpub_factory(authors=None)
        assert item.full_author_listing == ""

    def test_one_author(self, journalpub_factory, author):
        item = journalpub_factory(authors=[author])
        assert ">Albert Einstein</a>" in item.full_author_listing
        # No trailing " and" or commas for a single author.
        assert " and " not in item.full_author_listing

    def test_two_authors_use_and(self, journalpub_factory, two_authors):
        item = journalpub_factory(authors=two_authors)
        out = item.full_author_listing
        assert " and " in out
        assert ", " not in out  # no comma between exactly two

    def test_three_authors_use_oxford_and(self, journalpub_factory, three_authors):
        item = journalpub_factory(authors=three_authors)
        out = item.full_author_listing
        # "<a>Joyce</a>, <a>Smith</a> and <a>Smythe</a>"
        assert ", " in out
        assert " and " in out


@pytest.mark.django_db
class TestFullEditorListing:
    """Editor byline on Book. Same English-list-join as authors."""

    def test_no_editors_renders_empty(self, book_factory, author):
        # No editors set on the M2M.
        book = book_factory(authors=[author])
        assert book.full_editor_listing == ""

    def test_one_editor(self, book_factory, two_authors):
        book = book_factory(authors=None, editors=[two_authors[0]])
        assert ">Albert Einstein</a>" in book.full_editor_listing

    def test_two_editors(self, book_factory, two_authors):
        book = book_factory(authors=None, editors=two_authors)
        assert " and " in book.full_editor_listing
        assert ", " not in book.full_editor_listing


@pytest.mark.django_db
class TestBookFullCitation:
    """Issue #29: book citation should mention editors and not mangle the
    edition string."""

    def test_authored_book(self, book_factory, author):
        cit = book_factory(authors=[author], edition="").full_citation()
        # Authored book without an edition: "<authors>: "<i>Title</i>", <publisher>, <year>."
        assert ">Albert Einstein</a>:" in cit
        assert "(ed.)" not in cit
        assert "(eds.)" not in cit

    def test_edited_volume_renders_eds_suffix(self, book_factory, two_authors):
        cit = book_factory(authors=None, editors=two_authors).full_citation()
        assert "(eds.)" in cit
        # Single colon between byline and title; not "<editors>: <editors> (eds.)"
        assert cit.count("(eds.)") == 1

    def test_single_editor_renders_singular_suffix(self, book_factory, author):
        cit = book_factory(authors=None, editors=[author]).full_citation()
        assert "(ed.)" in cit
        assert "(eds.)" not in cit

    def test_authored_with_editors_appends_eds(self, book_factory, author, two_authors):
        # An authored monograph in an edited series — both bylines render.
        cit = book_factory(authors=[author], editors=two_authors).full_citation()
        assert "(eds.)" in cit
        assert "; " in cit  # author and editor blocks separated by ";"

    def test_edition_is_not_per_char_stripped(self, book_factory, author):
        # Issue #29 latent bug: pre-fix code did
        # `self.edition.lower().rstrip("edition")` which is a per-character
        # rstrip — "2nd edition" → "2nd " by accident; "2nd ed." → "2nd"
        # (the trailing ".d.e " characters all get stripped). Plus AttributeError
        # if edition is None, since `.lower()` was called before the truthy
        # check. Pin "2nd ed." renders as-is, no characters chewed off.
        cit = book_factory(authors=[author], edition="2nd ed.").full_citation()
        assert "2nd ed." in cit

    def test_no_edition_no_attribute_error(self, book_factory, author):
        # Pre-fix code crashed with AttributeError when edition was None
        # (it called `.lower()` before checking truthy). Now blank skips
        # the edition block cleanly.
        cit = book_factory(authors=[author], edition=None).full_citation()
        assert "Multivariate Calibration" in cit


@pytest.mark.django_db
class TestJournalUniqueName:
    """Issue #23: ``Journal.name`` is unique case-insensitively. Two
    rows whose names differ only in case can't coexist after migration
    0007 (the data merge folds existing duplicates into a survivor and
    the functional unique index prevents new ones)."""

    def test_distinct_names_can_coexist(self, db):
        from items.models import Journal

        Journal.objects.create(
            name="Analytica Chimica Acta", website="https://a.example"
        )
        Journal.objects.create(name="Chemometrics Journal", website="https://b.example")
        assert Journal.objects.count() == 2

    def test_case_insensitive_duplicate_rejected(self, db):
        from items.models import Journal

        Journal.objects.create(
            name="Analytica Chimica Acta", website="https://a.example"
        )
        with pytest.raises(IntegrityError):
            Journal.objects.create(
                name="analytica chimica acta", website="https://b.example"
            )


@pytest.mark.django_db
class TestDoiLinkNormalisation:
    """Issue #20: admins can paste either a full URL or a bare DOI suffix
    in the ``doi_link`` field. ``Item.save()`` normalises everything to
    ``https://doi.org/<suffix>`` so downstream code sees one shape only."""

    def test_bare_doi_suffix_gets_doi_org_prefix(self, journalpub_factory, author):
        item = journalpub_factory(authors=[author], doi_link="10.1234/foo-bar")
        assert item.doi_link == "https://doi.org/10.1234/foo-bar"

    def test_doi_org_without_scheme_gets_https_prefix(self, journalpub_factory, author):
        item = journalpub_factory(authors=[author], doi_link="doi.org/10.1234/foo")
        assert item.doi_link == "https://doi.org/10.1234/foo"

    def test_dx_doi_org_without_scheme_gets_https_prefix(
        self, journalpub_factory, author
    ):
        item = journalpub_factory(authors=[author], doi_link="dx.doi.org/10.1234/foo")
        assert item.doi_link == "https://dx.doi.org/10.1234/foo"

    def test_full_https_url_preserved(self, journalpub_factory, author):
        item = journalpub_factory(
            authors=[author], doi_link="https://doi.org/10.1234/foo"
        )
        assert item.doi_link == "https://doi.org/10.1234/foo"

    def test_full_http_url_preserved(self, journalpub_factory, author):
        item = journalpub_factory(
            authors=[author], doi_link="http://doi.org/10.1234/foo"
        )
        assert item.doi_link == "http://doi.org/10.1234/foo"

    def test_whitespace_stripped(self, journalpub_factory, author):
        item = journalpub_factory(authors=[author], doi_link="  10.1234/foo  ")
        assert item.doi_link == "https://doi.org/10.1234/foo"

    def test_validator_rejects_garbage(self, db):
        from django.core.exceptions import ValidationError

        from items.models import validate_doi_or_url

        with pytest.raises(ValidationError):
            validate_doi_or_url("not a url not a doi")

    def test_validator_accepts_bare_doi(self, db):
        from items.models import validate_doi_or_url

        # Should not raise.
        validate_doi_or_url("10.1234/foo-bar")

    def test_blank_doi_link_stays_empty(self, journalpub_factory, author):
        item = journalpub_factory(authors=[author], doi_link="")
        assert item.doi_link == ""


@pytest.mark.django_db
class TestInCollection:
    """Theme D (#14 + #31): book-chapter subclass with multi-table
    inheritance off Item. Same shape as Book / JournalPub / Thesis /
    ConferenceProceeding."""

    def test_full_citation_includes_chapter_and_book_titles(
        self, incollection_factory, author
    ):
        chap = incollection_factory(authors=[author], title="Chapter X")
        cit = chap.full_citation()
        # Chapter title (in quotes) and book title (italicised) both appear.
        assert "Chapter X" in cit
        assert "Multivariate Statistical Methods for Process Modelling" in cit
        assert "<i>Multivariate Statistical Methods for Process Modelling</i>" in cit

    def test_full_citation_renders_eds_suffix_for_editors(
        self, incollection_factory, two_authors
    ):
        chap = incollection_factory(authors=None, editors=two_authors)
        cit = chap.full_citation()
        assert "(eds.)" in cit
        assert "in " in cit  # "in <editors> (eds.), <book title>"

    def test_full_citation_singular_ed_for_one_editor(
        self, incollection_factory, author
    ):
        chap = incollection_factory(authors=None, editors=[author])
        cit = chap.full_citation()
        assert "(ed.)" in cit
        assert "(eds.)" not in cit

    def test_full_citation_renders_pages(self, incollection_factory, author):
        chap = incollection_factory(authors=[author], page_start="123", page_end="155")
        assert "pp. 123" in chap.full_citation()

    def test_no_authors_no_crash(self, incollection_factory):
        # Issue #35-shape regression: InCollection should not blow up
        # on a 0-author item; full_author_listing returns "" cleanly.
        chap = incollection_factory(authors=None, title="Anonymous chapter")
        cit = chap.full_citation()
        assert "Anonymous chapter" in cit


@pytest.mark.django_db
class TestDoiLinkCleaned:
    def test_strips_https_dx_doi_org(self, journalpub_factory):
        item = journalpub_factory(doi_link="https://dx.doi.org/10.1234/foo")
        assert item.doi_link_cleaned == "10.1234/foo"

    def test_strips_http_dx_doi_org(self, journalpub_factory):
        item = journalpub_factory(doi_link="http://dx.doi.org/10.1234/foo")
        assert item.doi_link_cleaned == "10.1234/foo"

    def test_strips_https_doi_org(self, journalpub_factory):
        item = journalpub_factory(doi_link="https://doi.org/10.1234/foo")
        assert item.doi_link_cleaned == "10.1234/foo"

    def test_strips_http_doi_org(self, journalpub_factory):
        item = journalpub_factory(doi_link="http://doi.org/10.1234/foo")
        assert item.doi_link_cleaned == "10.1234/foo"

    def test_does_not_strip_per_character(self, journalpub_factory):
        """Phase 1 fixed a latent bug: the legacy `.lstrip('http://dx.doi.org/')`
        was a per-character strip that ate any DOI starting with one of those
        characters. The replacement is a true prefix strip.
        """
        item = journalpub_factory(doi_link="https://example.org/h0me")
        # Should NOT be stripped (no matching prefix).
        assert item.doi_link_cleaned == "https://example.org/h0me"


@pytest.mark.django_db
class TestItemSlugAndCitation:
    def test_slug_generated_from_title(self, journalpub_factory):
        item = journalpub_factory(title="On the Fourier transform")
        assert item.slug == "on-the-fourier-transform"

    def test_full_citation_includes_title_year_journal(
        self, journalpub_factory, author
    ):
        item = journalpub_factory(
            authors=[author],
            title="A study",
            year=2024,
            volume="12",
            page_start="1",
            page_end="9",
        )
        cit = item.full_citation()
        assert "A study" in cit
        assert "2024" in cit
        assert "Test Journal" in cit
        assert "12" in cit
        assert "1-9" in cit

    def test_has_extra_reflects_other_search_text(self, journalpub_factory):
        no_extra = journalpub_factory(title="Without extra")
        assert no_extra.has_extra is False

        with_extra = journalpub_factory(
            title="With extra", other_search_text="full PDF text here"
        )
        assert with_extra.has_extra is True
