"""Tests for ``manage.py export_references``.

Exercises each output format (JSON / markdown / text) and each Item
subclass (JournalPub / Book / ConferenceProceeding / Thesis /
InCollection) to confirm the venue rendering branches all fire.
"""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from items.models import Author, AuthorGroup, ConferenceProceeding, School, Thesis


def run_export(format="json", base_url=None):
    out = StringIO()
    args = ["export_references", "--format", format]
    if base_url is not None:
        args += ["--base-url", base_url]
    call_command(*args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestExportReferencesJson:
    def test_empty_corpus_emits_empty_array(self, db):
        assert json.loads(run_export()) == []

    def test_journalpub_record_shape(self, journalpub_factory, author):
        journalpub_factory(
            authors=[author],
            title="On Fourier transforms",
            year=2024,
            volume="42",
            page_start="1",
            page_end="9",
            doi_link="https://doi.org/10.1234/foo",
        )
        records = json.loads(run_export())
        assert len(records) == 1
        r = records[0]
        assert r["type"] == "journalpub"
        assert r["title"] == "On Fourier transforms"
        assert r["authors"] == ["Albert Einstein"]
        assert r["year"] == 2024
        assert "Test Journal" in r["venue"]  # journal fixture name
        assert "vol. 42" in r["venue"]
        assert "pp. 1-9" in r["venue"]
        assert r["doi"] == "https://doi.org/10.1234/foo"
        assert r["url"].startswith("https://literature.learnche.org/item/")
        assert r["url"].endswith("/on-fourier-transforms")

    def test_book_record_shape(self, book_factory, author):
        book_factory(
            authors=[author],
            title="Multivariate Calibration",
            year=2017,
            isbn="978-1-234-56789-0",
        )
        records = json.loads(run_export())
        r = records[0]
        assert r["type"] == "book"
        assert "ISBN 978-1-234-56789-0" in r["venue"]
        assert "Test Publisher" in r["venue"]

    def test_conference_record_shape(self, db, author):
        proc = ConferenceProceeding.objects.create(
            title="Some proceedings paper",
            item_type="conferenceproc",
            year=2014,
            conference_name="MACC",
            organization="McMaster",
            location="Hamilton",
            page_start="100",
            page_end="120",
        )
        AuthorGroup.objects.create(author=author, item=proc, order=0)
        records = json.loads(run_export())
        r = records[0]
        assert r["type"] == "conferenceproc"
        assert "MACC" in r["venue"]
        assert "Hamilton" in r["venue"]
        assert "pp. 100-120" in r["venue"]

    def test_thesis_record_shape(self, db, author):
        school = School.objects.create(name="McMaster University")
        thesis = Thesis.objects.create(
            title="A novel batch process model",
            item_type="thesis",
            year=2018,
            thesis_type="phd",
            school=school,
        )
        AuthorGroup.objects.create(author=author, item=thesis, order=0)
        records = json.loads(run_export())
        r = records[0]
        assert r["type"] == "thesis"
        assert "Ph.D thesis" in r["venue"]
        assert "McMaster University" in r["venue"]

    def test_incollection_record_shape(self, incollection_factory, author):
        incollection_factory(
            authors=[author],
            title="A chapter",
            book_title="Statistical Methods in Chemometrics",
            page_start="55",
            page_end="80",
        )
        records = json.loads(run_export())
        r = records[0]
        assert r["type"] == "incollection"
        assert 'in "Statistical Methods in Chemometrics"' in r["venue"]
        assert "pp. 55-80" in r["venue"]

    def test_zero_authors_does_not_crash(self, journalpub_factory):
        journalpub_factory(authors=None, title="Anonymous paper")
        records = json.loads(run_export())
        assert records[0]["authors"] == []

    def test_base_url_override(self, journalpub_factory, author):
        journalpub_factory(authors=[author])
        records = json.loads(run_export(base_url="https://staging.example.com"))
        assert records[0]["url"].startswith("https://staging.example.com/item/")

    def test_records_ordered_by_year(self, journalpub_factory, author):
        journalpub_factory(authors=[author], title="Newer", year=2024)
        journalpub_factory(authors=[author], title="Older", year=2010)
        records = json.loads(run_export())
        assert [r["year"] for r in records] == [2010, 2024]


@pytest.mark.django_db
class TestExportReferencesMarkdown:
    def test_markdown_format_per_line(self, journalpub_factory, author):
        journalpub_factory(
            authors=[author],
            title="On Fourier transforms",
            year=2024,
            doi_link="https://doi.org/10.1234/foo",
        )
        out = run_export(format="markdown")
        # One line, kicked off with the [id] tag, ends with a Reference link.
        assert "**[" in out
        assert "Albert Einstein" in out
        assert "_On Fourier transforms_" in out
        assert "DOI: https://doi.org/10.1234/foo" in out
        assert "[Reference](https://literature.learnche.org/item/" in out

    def test_markdown_handles_no_authors(self, journalpub_factory):
        journalpub_factory(authors=None, title="Anonymous paper")
        out = run_export(format="markdown")
        assert "[no authors]" in out


@pytest.mark.django_db
class TestExportReferencesText:
    def test_text_format_one_line_per_item(self, journalpub_factory, author):
        a2 = Author.objects.create(first_name="Marie", last_name="Curie")
        journalpub_factory(authors=[author, a2], title="A paper", year=2020)
        out = run_export(format="text").strip().splitlines()
        assert len(out) == 1
        line = out[0]
        assert "[" in line and "]" in line  # the [id] tag
        assert "Albert Einstein, Marie Curie" in line
        assert "(2020)." in line
        assert '"A paper".' in line
        assert "URL: https://literature.learnche.org/item/" in line
