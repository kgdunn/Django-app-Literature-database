"""Import a Django ``dumpdata --all`` JSON snapshot from the legacy
literature install (the connectmv.com / Mercurial-era 2010-2018 site)
into the current Phase-1+ schema.

The command is **idempotent**: re-running against an already-populated
database updates rows in place rather than creating duplicates. Legacy
primary keys are preserved (so existing links into specific items keep
working after import).

Behavioural notes the import handles for you:

* The legacy `Item.pdf_file` paths started with ``media/...``; the new
  ``upload_to`` writes ``literature/pdf/...`` (no ``media/`` prefix).
  The command strips the prefix.
* Phase 5 dropped ``Item.private_pdf`` and ``Item.can_show_pdf``;
  Phase 4 dropped ``PageHit.ua_string`` and ``PageHit.ip_address``.
  These fields are silently ignored if present in the dump.
* Multi-table inheritance: each ``Item`` in the dump is paired with
  exactly one subclass record (``items.journalpub`` / ``items.book`` /
  ``items.conferenceproceeding`` / ``items.thesis``). The command
  merges parent + subclass fields and creates the subclass directly,
  so Django's auto-Item-row machinery doesn't double-write.
* Auth / contenttypes / sessions / admin records in a ``--all`` dump
  are skipped — the new install has its own.

Usage::

    # Extract the backup tarball first:
    tar -xjf Literature-full-backup--YYYY-MM-DD-HH-MM-SS.tar.bz2
    # Find the dumpdata JSON (path varies by tarball layout):
    find . -name 'Literature--DjangoDump--*.json'
    # Then import:
    uv run python manage.py import_legacy_dump --file path/to/legacy.json

    # Dry-run first to see what would change:
    uv run python manage.py import_legacy_dump --file legacy.json --dry-run
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction

from items.models import (
    Author,
    AuthorGroup,
    Book,
    ConferenceProceeding,
    Item,
    Journal,
    JournalPub,
    Publisher,
    School,
    Thesis,
)
from pagehit.models import PageHit
from tagging.models import Tag

logger = logging.getLogger(__name__)


# Models that the new install owns — auth / contenttypes / sessions /
# admin records in a `--all` dump are dropped on the floor.
_ITEM_SUBCLASSES = {
    "items.journalpub": JournalPub,
    "items.book": Book,
    "items.conferenceproceeding": ConferenceProceeding,
    "items.thesis": Thesis,
}

_LOOKUP_MODELS = {
    "items.author": Author,
    "items.journal": Journal,
    "items.publisher": Publisher,
    "items.school": School,
    "tagging.tag": Tag,
}

# Fields that were dropped in Phase 4 / Phase 5 and must not be passed
# to the constructor of the new model.
_DROPPED_FIELDS = {
    "items.item": {"private_pdf", "can_show_pdf"},
    "pagehit.pagehit": {"ua_string", "ip_address"},
}

# Fields handled separately (M2M, reverse FKs, multi-table-inheritance
# parent links) — pulled out before passing the dict to ``**kwargs``.
_M2M_FIELDS = {
    "items.item": ("tags", "authors"),
    "items.book": ("editors",),
    "items.conferenceproceeding": ("editors",),
    "items.thesis": ("supervisors",),
}

# Subclass-only M2Ms that get applied AFTER the parent + subclass rows
# exist. The handler iterates these in `_apply_subclass_m2ms`.
_SUBCLASSES_WITH_AUTHOR_M2M = (
    "items.book",
    "items.conferenceproceeding",
    "items.thesis",
)


class Command(BaseCommand):
    help = "Import a legacy `dumpdata --all` JSON snapshot."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            required=True,
            help="Path to the dumpdata JSON file (extracted from the legacy "
            "backup tarball).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse the dump and report what would change, without "
            "writing to the database.",
        )

    def handle(self, *args, **options):
        records = self._load_dump(Path(options["file"]))
        by_model = self._index_by_model(records)
        item_parents: dict[int, dict[str, Any]] = {
            r["pk"]: r["fields"] for r in by_model.get("items.item", [])
        }

        dry = options["dry_run"]
        counts: Counter[str] = Counter()

        with transaction.atomic():
            sid = transaction.savepoint()

            self._import_lookup_models(by_model, dry=dry, counts=counts)
            self._import_subclasses(by_model, item_parents, dry=dry, counts=counts)
            self._apply_item_tags(by_model, dry=dry, counts=counts)
            self._apply_subclass_m2ms(by_model, dry=dry, counts=counts)
            self._import_authorgroups(by_model, dry=dry, counts=counts)
            self._import_pagehits(by_model, dry=dry, counts=counts)

            if dry:
                # Roll back so the database is untouched.
                transaction.savepoint_rollback(sid)
            else:
                transaction.savepoint_commit(sid)

        if not dry:
            self._reset_sequences()

        self._print_summary(counts, dry=dry)

    def _reset_sequences(self) -> None:
        # Rows are inserted with explicit legacy pks, which leaves each
        # table's auto-increment sequence at 1. Without this bump, the
        # next insert from a real request collides on the PK and the
        # view 500s — see RELEASES.md v1.0.3 for the live-site postmortem.
        # We call the underlying ops API rather than `sqlsequencereset`
        # because the management command wraps its output in BEGIN/COMMIT,
        # which would commit any enclosing transaction (including
        # pytest-django's per-test transaction) mid-flight.
        style = no_style()
        statements: list[str] = []
        for app_label in ("items", "pagehit", "tagging"):
            models = apps.get_app_config(app_label).get_models()
            statements.extend(connection.ops.sequence_reset_sql(style, models))
        if not statements:
            return
        with connection.cursor() as cursor:
            for stmt in statements:
                cursor.execute(stmt)

    # -------- input loading ---------------------------------------

    def _load_dump(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise CommandError(f"Dump file does not exist: {path}")
        try:
            with path.open() as f:
                records = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Could not parse {path} as JSON: {e}") from e
        if not isinstance(records, list):
            raise CommandError(
                f"Expected a JSON array (Django dumpdata format); got "
                f"{type(records).__name__}."
            )
        return records

    def _index_by_model(
        self, records: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in records:
            model = r.get("model")
            if model:
                by_model[model.lower()].append(r)
        return by_model

    # -------- per-model passes ------------------------------------

    def _import_lookup_models(
        self,
        by_model: dict[str, list[dict[str, Any]]],
        *,
        dry: bool,
        counts: Counter,
    ) -> None:
        """Author / Journal / Publisher / School / Tag — no FKs to anything
        else in this set, so order within the loop doesn't matter.
        """
        for model_label, model_cls in _LOOKUP_MODELS.items():
            for r in by_model.get(model_label, []):
                self._upsert(
                    model_cls,
                    r["pk"],
                    r["fields"],
                    dry=dry,
                    model_label=model_label,
                    counts=counts,
                )

    def _import_subclasses(
        self,
        by_model: dict[str, list[dict[str, Any]]],
        item_parents: dict[int, dict[str, Any]],
        *,
        dry: bool,
        counts: Counter,
    ) -> None:
        """Multi-table-inheritance pass: for each subclass record, look up
        its parent ``items.item`` fields, merge, then upsert the subclass
        with the legacy pk so Django populates both the parent and
        subclass rows in one shot.
        """
        for subclass_label, subclass_cls in _ITEM_SUBCLASSES.items():
            for r in by_model.get(subclass_label, []):
                parent = item_parents.get(r["pk"])
                if parent is None:
                    self._warn_orphan_subclass(subclass_label, r["pk"])
                    continue
                merged = self._merge_item_fields(parent, r["fields"])
                self._upsert(
                    subclass_cls,
                    r["pk"],
                    merged,
                    dry=dry,
                    model_label=subclass_label,
                    counts=counts,
                    parent_label="items.item",
                )

    def _warn_orphan_subclass(self, subclass_label: str, pk: int) -> None:
        self.stdout.write(
            self.style.WARNING(
                f"  [skip] {subclass_label} pk={pk}: no matching items.item record"
            )
        )

    def _apply_item_tags(
        self,
        by_model: dict[str, list[dict[str, Any]]],
        *,
        dry: bool,
        counts: Counter,
    ) -> None:
        """Set Item.tags M2Ms once parent rows exist. The fields list comes
        from the ``items.item`` record (subclass records don't carry it).
        """
        for r in by_model.get("items.item", []):
            tag_pks = r["fields"].get("tags") or []
            if not tag_pks:
                continue
            counts["m2m: items.item.tags"] += len(tag_pks)
            if dry:
                continue
            item = Item.objects.filter(pk=r["pk"]).first()
            if item is not None:
                item.tags.set(Tag.objects.filter(pk__in=tag_pks))

    def _apply_subclass_m2ms(
        self,
        by_model: dict[str, list[dict[str, Any]]],
        *,
        dry: bool,
        counts: Counter,
    ) -> None:
        """Book.editors / ConferenceProceeding.editors / Thesis.supervisors.
        All three resolve to ``Author`` queries.
        """
        for label in _SUBCLASSES_WITH_AUTHOR_M2M:
            m2m_names = _M2M_FIELDS.get(label, ())
            for r in by_model.get(label, []):
                self._apply_one_subclass_record_m2ms(
                    label, r, m2m_names, dry=dry, counts=counts
                )

    def _apply_one_subclass_record_m2ms(
        self,
        label: str,
        record: dict[str, Any],
        m2m_names: tuple[str, ...],
        *,
        dry: bool,
        counts: Counter,
    ) -> None:
        for m2m_name in m2m_names:
            related_pks = record["fields"].get(m2m_name) or []
            if not related_pks:
                continue
            counts[f"m2m: {label}.{m2m_name}"] += len(related_pks)
            if dry:
                continue
            obj = _ITEM_SUBCLASSES[label].objects.filter(pk=record["pk"]).first()
            if obj is not None:
                getattr(obj, m2m_name).set(Author.objects.filter(pk__in=related_pks))

    def _import_authorgroups(
        self,
        by_model: dict[str, list[dict[str, Any]]],
        *,
        dry: bool,
        counts: Counter,
    ) -> None:
        """AuthorGroup is the through-table linking Item.authors. Each row
        carries (author_id, item_id, order). Created last so both sides
        of the FK already exist.
        """
        for r in by_model.get("items.authorgroup", []):
            counts["items.authorgroup"] += 1
            if dry:
                continue
            fields = r["fields"]
            AuthorGroup.objects.update_or_create(
                pk=r["pk"],
                defaults={
                    "author_id": fields["author"],
                    "item_id": fields["item"],
                    "order": fields.get("order", 0),
                },
            )

    def _import_pagehits(
        self,
        by_model: dict[str, list[dict[str, Any]]],
        *,
        dry: bool,
        counts: Counter,
    ) -> None:
        for r in by_model.get("pagehit.pagehit", []):
            self._upsert(
                PageHit,
                r["pk"],
                self._strip_dropped("pagehit.pagehit", r["fields"]),
                dry=dry,
                model_label="pagehit.pagehit",
                counts=counts,
            )

    # -------- per-record helpers ----------------------------------

    def _merge_item_fields(
        self, parent_fields: dict[str, Any], subclass_fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge parent ``items.item`` fields with subclass fields. The
        subclass record's ``item_ptr`` is dropped (Django sets that
        automatically when we save the subclass with ``pk=<legacy id>``).
        Tags / authors M2Ms are also dropped here — they're applied in a
        separate pass after the parent rows exist.
        """
        merged = dict(parent_fields)
        merged.update(subclass_fields)
        merged.pop("item_ptr", None)
        for f in _M2M_FIELDS.get("items.item", ()):
            merged.pop(f, None)
        # Subclass-specific M2Ms also get applied later.
        merged.pop("editors", None)
        merged.pop("supervisors", None)
        # Strip Phase-4/5 dropped fields if present in the dump.
        merged = self._strip_dropped("items.item", merged)
        # Strip the legacy `media/` prefix from pdf_file paths
        # (Phase-5 / Phase-1 gotcha: new upload_to writes
        # `literature/pdf/<slug[0]>/<slug>.pdf`, no `media/` prefix).
        if merged.get("pdf_file"):
            merged["pdf_file"] = merged["pdf_file"].removeprefix("media/")
        return merged

    def _strip_dropped(
        self, model_label: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        dropped = _DROPPED_FIELDS.get(model_label, set())
        return {k: v for k, v in fields.items() if k not in dropped}

    def _upsert(
        self,
        model_cls,
        pk: int,
        fields: dict[str, Any],
        *,
        dry: bool,
        model_label: str,
        counts: Counter,
        parent_label: str | None = None,
    ) -> None:
        if dry:
            counts[model_label] += 1
            return
        # Translate any FK fields to their _id form so we can pass them
        # straight into update_or_create defaults.
        defaults = {}
        for k, v in fields.items():
            field_obj = self._get_field(model_cls, k)
            if field_obj is None:
                continue
            if field_obj.is_relation and not field_obj.many_to_many:
                defaults[f"{k}_id"] = v
            else:
                defaults[k] = v
        model_cls.objects.update_or_create(pk=pk, defaults=defaults)
        counts[model_label] += 1

    def _get_field(self, model_cls, name: str):
        try:
            return model_cls._meta.get_field(name)
        except Exception:
            return None

    def _print_summary(self, counts: Counter, *, dry: bool) -> None:
        verb = "Would import" if dry else "Imported"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{verb}:"))
        for label, n in sorted(counts.items()):
            self.stdout.write(f"  {label}: {n}")
        self.stdout.write("")
