"""Tests for the items domain layer (models + properties)."""

import pytest

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
