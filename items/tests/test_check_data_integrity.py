"""Tests for ``manage.py check_data_integrity`` (issue #25).

Exercises the three warning kinds the command can emit:
  - missing PDF on disk
  - all-zero AuthorGroup ordering (legacy import artefact)
  - zero authors

Plus the clean-corpus path (no warnings) and the ``--verbose`` flag.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from items.models import Author, AuthorGroup


def run_check(verbose=False):
    out = StringIO()
    args = ["check_data_integrity"]
    if verbose:
        args.append("--verbose")
    call_command(*args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestCheckDataIntegrity:
    def test_clean_corpus_emits_no_warnings(self, journalpub_factory, author):
        """Single item, single author, no PDF — should report 0 issues."""
        journalpub_factory(authors=[author])
        out = run_check()
        assert "[summary] 1 items checked, 0 issues" in out
        assert "[pdf-missing]" not in out
        assert "[author-order-zero]" not in out
        assert "[no-authors]" not in out

    def test_missing_pdf_warning(
        self, journalpub_factory, author, db, settings, tmp_path
    ):
        """An item whose ``pdf_file`` points at a non-existent path on disk
        is flagged under ``[pdf-missing]``."""
        settings.MEDIA_ROOT = str(tmp_path)
        item = journalpub_factory(
            authors=[author], title="Ghost paper", pdf_file="literature/pdf/g/ghost.pdf"
        )
        out = run_check()
        assert "[pdf-missing]" in out
        assert f"item {item.id}" in out
        assert "Ghost paper" in out
        assert "literature/pdf/g/ghost.pdf" in out

    def test_existing_pdf_no_warning(
        self, journalpub_factory, author, settings, tmp_path
    ):
        """When the file genuinely exists at MEDIA_ROOT/<pdf_file>, no warning."""
        settings.MEDIA_ROOT = str(tmp_path)
        target_dir = tmp_path / "literature" / "pdf" / "h"
        target_dir.mkdir(parents=True)
        (target_dir / "here.pdf").write_bytes(b"%PDF-1.4 stub")
        journalpub_factory(authors=[author], pdf_file="literature/pdf/h/here.pdf")
        out = run_check()
        assert "[pdf-missing]" not in out

    def test_all_zero_author_order_warning(self, journalpub_factory, db):
        """Multi-author item where every AuthorGroup has order=0 (legacy
        default) is flagged under ``[author-order-zero]``."""
        a1 = Author.objects.create(first_name="A", last_name="Alpha")
        a2 = Author.objects.create(first_name="B", last_name="Beta")
        item = journalpub_factory(authors=None, title="Bad ordering")
        # Create AuthorGroup rows directly with order=0.
        AuthorGroup.objects.create(author=a1, item=item, order=0)
        AuthorGroup.objects.create(author=a2, item=item, order=0)
        out = run_check()
        assert "[author-order-zero]" in out
        assert f"item {item.id}" in out
        assert "Bad ordering" in out

    def test_single_author_with_order_zero_not_flagged(
        self, journalpub_factory, author
    ):
        """Single-author items legitimately have order=0; no warning."""
        journalpub_factory(authors=[author])  # default order=0 for single
        out = run_check()
        assert "[author-order-zero]" not in out

    def test_no_authors_warning(self, journalpub_factory):
        """An item with zero AuthorGroup rows is flagged under
        ``[no-authors]``."""
        item = journalpub_factory(authors=None, title="Orphan")
        out = run_check()
        assert "[no-authors]" in out
        assert f"item {item.id}" in out
        assert "Orphan" in out

    def test_summary_counts_all_warnings(self, journalpub_factory, author, db):
        """The summary line aggregates the three counters."""
        # Item 1: clean
        journalpub_factory(authors=[author], title="Clean")
        # Item 2: missing PDF
        journalpub_factory(
            authors=[author],
            title="Missing PDF",
            pdf_file="literature/pdf/m/missing.pdf",
        )
        # Item 3: orphan (no authors)
        journalpub_factory(authors=None, title="Orphan")

        out = run_check()
        assert "3 items checked" in out
        assert "1 pdf-missing" in out
        assert "1 no-authors" in out

    def test_verbose_lists_each_item(self, journalpub_factory, author):
        journalpub_factory(authors=[author], title="One")
        journalpub_factory(authors=[author], title="Two")
        out = run_check(verbose=True)
        assert "checking item" in out
        assert "'One'" in out
        assert "'Two'" in out

    def test_verbose_omitted_by_default(self, journalpub_factory, author):
        journalpub_factory(authors=[author], title="One")
        out = run_check(verbose=False)
        assert "checking item" not in out
