"""Export the full reference list as JSON / Markdown / plain text.

Designed to be piped into a Claude prompt for "find places in this
textbook where these references could be cited" workflows. Each
record carries the catalogue URL so the edited book can link
directly back to the per-item detail page on literature.learnche.org.

Usage on the Hetzner host::

    cd /home/deploy/literature/repo
    docker compose -f docker-compose.prod.yml exec web \\
        python manage.py export_references --format json > refs.json

Or for a human-skimmable list::

    docker compose -f docker-compose.prod.yml exec web \\
        python manage.py export_references --format markdown > refs.md
"""

import json

from django.core.management.base import BaseCommand

from items.models import (
    AuthorGroup,
    Book,
    ConferenceProceeding,
    InCollection,
    Item,
    JournalPub,
    Thesis,
)


def _authors(item):
    """Ordered list of author full-name strings for an Item."""
    rows = (
        AuthorGroup.objects.filter(item=item)
        .order_by("order", "id")
        .select_related("author")
    )
    return [a.author.full_name for a in rows]


def _venue(item):
    """One-line description of where the item was published.

    Branches by ``item.item_type`` and pulls the relevant subclass
    fields (journal, publisher + ISBN, conference details, school,
    parent book). Returns "" if the subclass row is missing — defensive
    for legacy data where the typed row hasn't been created.
    """
    if item.item_type == "journalpub":
        sub = JournalPub.objects.filter(pk=item.pk).select_related("journal").first()
        if not sub:
            return ""
        parts = [sub.journal.name]
        if sub.volume:
            parts.append(f"vol. {sub.volume}")
        if sub.page_start and sub.page_end:
            parts.append(f"pp. {sub.page_start}-{sub.page_end}")
        elif sub.page_start:
            parts.append(f"p. {sub.page_start}")
        return ", ".join(parts)

    if item.item_type == "book":
        sub = Book.objects.filter(pk=item.pk).select_related("publisher").first()
        if not sub:
            return ""
        parts = []
        if sub.edition:
            parts.append(sub.edition)
        if sub.publisher:
            parts.append(sub.publisher.name)
        if sub.isbn:
            parts.append(f"ISBN {sub.isbn}")
        return ", ".join(parts)

    if item.item_type == "conferenceproc":
        sub = (
            ConferenceProceeding.objects.filter(pk=item.pk)
            .select_related("publisher")
            .first()
        )
        if not sub:
            return ""
        parts = [p for p in [sub.conference_name, sub.organization, sub.location] if p]
        if sub.page_start and sub.page_end:
            parts.append(f"pp. {sub.page_start}-{sub.page_end}")
        if sub.publisher:
            parts.append(sub.publisher.name)
        return ", ".join(parts)

    if item.item_type == "thesis":
        sub = Thesis.objects.filter(pk=item.pk).select_related("school").first()
        if not sub:
            return ""
        thesis_type = dict(Thesis.THESIS_CHOICES).get(sub.thesis_type, sub.thesis_type)
        return f"{thesis_type}, {sub.school.name}"

    if item.item_type == "incollection":
        sub = (
            InCollection.objects.filter(pk=item.pk).select_related("publisher").first()
        )
        if not sub:
            return ""
        parts = [f'in "{sub.book_title}"']
        if sub.edition:
            parts.append(sub.edition)
        if sub.publisher:
            parts.append(sub.publisher.name)
        if sub.page_start and sub.page_end:
            parts.append(f"pp. {sub.page_start}-{sub.page_end}")
        return ", ".join(parts)

    return ""


class Command(BaseCommand):
    help = "Dump the full reference list as JSON / Markdown / plain text."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["json", "markdown", "text"],
            default="json",
            help=(
                "Output format. JSON is best for feeding to a language model; "
                "markdown is best for human skimming; text is a one-line-per-"
                "item compact form."
            ),
        )
        parser.add_argument(
            "--base-url",
            default="https://literature.learnche.org",
            help=(
                "Site base URL to prefix item links with. Override only if "
                "running against a non-prod deployment."
            ),
        )

    def handle(self, *args, format, base_url, **options):
        base_url = base_url.rstrip("/")
        records = []
        for item in Item.objects.all().order_by("year", "id"):
            url = f"{base_url}/item/{item.pk}/{item.slug}"
            records.append(
                {
                    "id": item.pk,
                    "type": item.item_type,
                    "title": (item.title or "").strip(),
                    "authors": _authors(item),
                    "year": item.year,
                    "venue": _venue(item),
                    "doi": item.doi_link or "",
                    "url": url,
                }
            )

        if format == "json":
            self.stdout.write(json.dumps(records, indent=2, ensure_ascii=False))
            return

        if format == "markdown":
            for r in records:
                authors = ", ".join(r["authors"]) if r["authors"] else "[no authors]"
                line = f"- **[{r['id']}]** {authors} ({r['year']}). _{r['title']}_."
                if r["venue"]:
                    line += f" {r['venue']}."
                if r["doi"]:
                    line += f" DOI: {r['doi']}."
                line += f" [Reference]({r['url']})"
                self.stdout.write(line)
            return

        # plain text — one item per line, suitable for grep / awk
        for r in records:
            authors = ", ".join(r["authors"]) if r["authors"] else "[no authors]"
            parts = [
                f"[{r['id']}]",
                authors,
                f"({r['year']}).",
                f'"{r["title"]}".',
            ]
            if r["venue"]:
                parts.append(r["venue"] + ".")
            if r["doi"]:
                parts.append(f"DOI: {r['doi']}.")
            parts.append(f"URL: {r['url']}")
            self.stdout.write(" ".join(parts))
