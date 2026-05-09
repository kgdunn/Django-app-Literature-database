"""Periodic data-integrity check (issue #25).

Walks the catalogue and flags items whose fields are out of sync with
the filesystem or that show signs of a botched legacy import:

  - ``pdf_file`` references a path that doesn't exist on disk.
  - All ``AuthorGroup`` rows for an item have ``order=0`` (the legacy
    default — means the author ordering was lost during import).
  - The item has zero authors at all (rare; left as a soft warning).

Designed to run as a daily / weekly cron under ``deploy``:

    docker compose -f docker-compose.prod.yml exec web \\
        python manage.py check_data_integrity \\
        >> /home/deploy/literature/backups/data-integrity.log 2>&1

The script is intentionally read-only — it never modifies the DB.
Always exits 0 so cron doesn't spam an alert on every run; the
operator reads the log on their own cadence.
"""

import os
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand

from items.models import AuthorGroup, Item


class Command(BaseCommand):
    help = "Walk every Item and report data-integrity warnings."

    def add_arguments(self, parser):
        # NB: don't add `-v` as a short flag — Django's BaseCommand already
        # registers `-v` for `--verbosity`, and argparse refuses
        # conflicting short options.
        parser.add_argument(
            "--verbose",
            action="store_true",
            default=False,
            help="Print one line per item checked, not just the warnings.",
        )

    def handle(self, *args, verbose=False, **options):
        started = datetime.now(timezone.utc)
        items = Item.objects.all().only(
            "id", "title", "pdf_file"
        )  # author_order pulled separately
        total = items.count()

        media_root = settings.MEDIA_ROOT
        warnings_pdf = []
        warnings_order = []
        warnings_no_authors = []

        self.stdout.write(
            "[check_data_integrity] %s starting; items=%d"
            % (started.isoformat(), total)
        )

        for item in items.iterator():
            if verbose:
                self.stdout.write(f"  checking item {item.id}: {item.title!r}")

            if item.pdf_file:
                # FileField stores the path relative to MEDIA_ROOT.
                disk_path = os.path.join(media_root, item.pdf_file.name)
                if not os.path.isfile(disk_path):
                    warnings_pdf.append((item.id, item.title, item.pdf_file.name))

            ag_qs = AuthorGroup.objects.filter(item=item)
            ag_count = ag_qs.count()
            if ag_count == 0:
                warnings_no_authors.append((item.id, item.title))
            elif ag_count > 1:
                # All-zero ordering is a legacy import artefact: every
                # author for that item shows up with order=0. A
                # single-author item legitimately has order=0 so we
                # skip the count==1 case.
                if not ag_qs.exclude(order=0).exists():
                    warnings_order.append((item.id, item.title, ag_count))

        if warnings_pdf:
            self.stdout.write("")
            self.stdout.write("[pdf-missing]")
            for pk, title, path in warnings_pdf:
                self.stdout.write(
                    "  item %d %r: pdf_file=%s — file not on disk" % (pk, title, path)
                )

        if warnings_order:
            self.stdout.write("")
            self.stdout.write("[author-order-zero]")
            for pk, title, n in warnings_order:
                self.stdout.write(
                    "  item %d %r: all %d authors have order=0" % (pk, title, n)
                )

        if warnings_no_authors:
            self.stdout.write("")
            self.stdout.write("[no-authors]")
            for pk, title in warnings_no_authors:
                self.stdout.write("  item %d %r: zero authors" % (pk, title))

        finished = datetime.now(timezone.utc)
        self.stdout.write("")
        self.stdout.write(
            "[summary] %d items checked, %d issues "
            "(%d pdf-missing, %d author-order-zero, %d no-authors)"
            % (
                total,
                len(warnings_pdf) + len(warnings_order) + len(warnings_no_authors),
                len(warnings_pdf),
                len(warnings_order),
                len(warnings_no_authors),
            )
        )
        self.stdout.write("[check_data_integrity] %s done" % finished.isoformat())
