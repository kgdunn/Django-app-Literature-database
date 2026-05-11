"""Tests for ``manage.py import_legacy_dump``.

The fixture is a small synthetic Django ``dumpdata --all``-style JSON
file written to a tmp_path. It covers each thing the import has to
handle:

- a lookup model (Author / Journal / Tag)
- multi-table inheritance (Item parent + JournalPub subclass)
- the through-table (AuthorGroup)
- M2M assignments (Item.tags)
- a PageHit row, including the Phase-4-dropped fields it must ignore
- a noise record (auth.user) that the importer should drop on the floor
- an Item with a ``media/`` prefix in pdf_file (Phase-1 gotcha)
- the dropped Phase-5 ``private_pdf`` / ``can_show_pdf`` fields and
  the v1.1.0-dropped ``show_abstract`` field
"""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from items.models import Author, AuthorGroup, Item, Journal, JournalPub
from pagehit.models import PageHit
from tagging.models import Tag


@pytest.fixture
def legacy_dump(tmp_path):
    """Synthetic dumpdata output covering each import code path."""
    records = [
        # --- noise: auth.* / contenttypes.* / sessions.* — dropped on floor.
        {"model": "auth.user", "pk": 1, "fields": {"username": "kgdunn"}},
        {
            "model": "contenttypes.contenttype",
            "pk": 1,
            "fields": {"app_label": "items"},
        },
        # --- lookup models
        {
            "model": "items.author",
            "pk": 12,
            "fields": {
                "first_name": "Albert",
                "middle_initials": None,
                "last_name": "Einstein",
                "slug": "albert-einstein",
            },
        },
        {
            "model": "items.journal",
            "pk": 3,
            "fields": {
                "name": "Journal of Chemometrics",
                "website": "https://example.com/jcg",
                "slug": "journal-of-chemometrics",
            },
        },
        {
            "model": "tagging.tag",
            "pk": 5,
            "fields": {"slug": "fourier", "name": "Fourier", "description": ""},
        },
        # --- Item parent + JournalPub subclass (multi-table inheritance)
        {
            "model": "items.item",
            "pk": 47,
            "fields": {
                "title": "On Fourier transforms",
                "slug": "on-fourier-transforms",
                "item_type": "journalpub",
                "year": 2014,
                "doi_link": "https://doi.org/10.1234/foo",
                "web_link": None,
                "abstract": "<p>A study.</p>",
                # v1.1.0-dropped field — silently ignored, same as the
                # Phase-5 / Phase-4 dropped fields below:
                "show_abstract": True,
                "pdf_file": "media/literature/pdf/o/on-fourier-transforms.pdf",
                "other_search_text": "extracted text",
                # Phase-5 dropped fields — must be silently ignored:
                "private_pdf": False,
                "can_show_pdf": True,
                # M2M via tags — applied in a separate pass:
                "tags": [5],
            },
        },
        {
            "model": "items.journalpub",
            "pk": 47,
            "fields": {
                "item_ptr": 47,  # ignored — Django sets it from pk
                "journal": 3,
                "volume": "12",
                "page_start": "1",
                "page_end": "9",
            },
        },
        # --- AuthorGroup through-row
        {
            "model": "items.authorgroup",
            "pk": 81,
            "fields": {"author": 12, "item": 47, "order": 0},
        },
        # --- PageHit, with Phase-4-dropped fields the import must skip
        {
            "model": "pagehit.pagehit",
            "pk": 998,
            "fields": {
                "datetime": "2018-01-15T12:00:00Z",
                "item": "item",
                "item_pk": 47,
                "extra_info": None,
                # Phase-4 dropped fields — must be silently ignored:
                "ua_string": "Mozilla/5.0 (X11; Linux x86_64) ...",
                "ip_address": "203.0.113.10",
            },
        },
    ]
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(records))
    return path


@pytest.mark.django_db
class TestImportLegacyDump:
    def test_dry_run_does_not_write(self, legacy_dump, capsys):
        call_command("import_legacy_dump", "--file", str(legacy_dump), "--dry-run")
        # Database is empty.
        assert Author.objects.count() == 0
        assert Item.objects.count() == 0
        assert JournalPub.objects.count() == 0
        assert AuthorGroup.objects.count() == 0
        assert PageHit.objects.count() == 0
        out = capsys.readouterr().out
        assert "Would import" in out

    def test_full_import_creates_expected_rows(self, legacy_dump):
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        assert Author.objects.count() == 1
        assert Journal.objects.count() == 1
        assert Tag.objects.count() == 1
        assert JournalPub.objects.count() == 1
        # Item.objects is the parent — JournalPub creation populates it
        # via multi-table inheritance.
        assert Item.objects.count() == 1
        assert AuthorGroup.objects.count() == 1
        assert PageHit.objects.count() == 1

    def test_legacy_pks_are_preserved(self, legacy_dump):
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        assert Author.objects.get(pk=12).last_name == "Einstein"
        assert Journal.objects.get(pk=3).name == "Journal of Chemometrics"
        assert Tag.objects.get(pk=5).name == "Fourier"
        assert JournalPub.objects.get(pk=47).title == "On Fourier transforms"
        assert AuthorGroup.objects.get(pk=81).order == 0

    def test_pdf_file_media_prefix_stripped(self, legacy_dump):
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        pub = JournalPub.objects.get(pk=47)
        assert pub.pdf_file.name == "literature/pdf/o/on-fourier-transforms.pdf"
        # `media/` prefix must NOT be retained.
        assert not pub.pdf_file.name.startswith("media/")

    def test_dropped_fields_are_silently_ignored(self, legacy_dump):
        # `private_pdf`, `can_show_pdf` (Phase 5), `show_abstract`
        # (v1.1.0) and `ua_string`, `ip_address` (Phase 4) are gone
        # from the model — the import must not crash on them and must
        # not try to set them.
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        # If we got here the import didn't FieldError. Confirm one row
        # of each surviving:
        assert PageHit.objects.get(pk=998).item == "item"
        assert JournalPub.objects.get(pk=47).year == 2014

    def test_subclass_resolution(self, legacy_dump):
        """The merged record should land in the JournalPub table, not just
        the abstract Item parent — `Item.objects.get(pk=47).journalpub`
        should resolve.
        """
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        pub = JournalPub.objects.get(pk=47)
        assert pub.journal_id == 3
        assert pub.volume == "12"
        assert pub.page_start == "1"
        assert pub.page_end == "9"
        # The reverse from Item also works:
        assert Item.objects.get(pk=47).item_type == "journalpub"

    def test_m2m_tags_assigned(self, legacy_dump):
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        pub = JournalPub.objects.get(pk=47)
        assert list(pub.tags.values_list("slug", flat=True)) == ["fourier"]

    def test_authorgroup_links_author_and_item(self, legacy_dump):
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        ag = AuthorGroup.objects.get(pk=81)
        assert ag.author.last_name == "Einstein"
        assert ag.item_id == 47
        # And the M2M-via-through resolves the reverse:
        assert "Einstein" in [
            a.last_name for a in JournalPub.objects.get(pk=47).authors.all()
        ]

    def test_idempotent_rerun(self, legacy_dump):
        """Running the import twice is a no-op (same row counts, same
        PKs). This is the primary safety guarantee — re-running on a
        partially-imported DB doesn't duplicate rows.
        """
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        call_command("import_legacy_dump", "--file", str(legacy_dump))
        assert Author.objects.count() == 1
        assert Journal.objects.count() == 1
        assert Tag.objects.count() == 1
        assert JournalPub.objects.count() == 1
        assert Item.objects.count() == 1
        assert AuthorGroup.objects.count() == 1
        assert PageHit.objects.count() == 1
        # And the PKs survived the rerun.
        assert JournalPub.objects.filter(pk=47).exists()

    def test_missing_file_errors_clearly(self, tmp_path):
        with pytest.raises(CommandError, match="does not exist"):
            call_command("import_legacy_dump", "--file", str(tmp_path / "nope.json"))

    def test_invalid_json_errors_clearly(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json at all")
        with pytest.raises(CommandError, match="Could not parse"):
            call_command("import_legacy_dump", "--file", str(bad))
