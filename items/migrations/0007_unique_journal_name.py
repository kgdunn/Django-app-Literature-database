"""Issue #23: case-insensitive uniqueness on ``Journal.name``.

Two operations:

1. **Data merge.** Walk every duplicate cluster (case-insensitive
   match on ``name``) and re-point all ``JournalPub.journal`` foreign
   keys to the survivor — the cluster's lowest-pk row, picked
   deterministically. The other rows are deleted.

2. **Functional unique constraint** ``UniqueConstraint(Lower("name"))``.
   Postgres builds a functional unique index on ``LOWER(name)``, so a
   future ``Journal.objects.create(name="Analytica Chimica Acta")``
   plus ``Journal.objects.create(name="analytica chimica acta")``
   raises ``IntegrityError`` instead of silently splitting the row.

The data merge is idempotent: if there are no duplicates, the loop
does nothing. The reverse migration drops the constraint but does
NOT attempt to un-merge — once collapsed, the original row identities
are gone (no ``legacy_id`` column on Journal).
"""

from django.db import migrations, models
from django.db.models.functions import Lower


def merge_duplicate_journals(apps, schema_editor):
    Journal = apps.get_model("items", "Journal")
    JournalPub = apps.get_model("items", "JournalPub")

    keepers = {}  # lowercased-name → survivor Journal instance
    duplicates = []  # (loser, survivor) pairs to re-point and delete

    for j in Journal.objects.order_by("pk"):
        key = (j.name or "").strip().lower()
        if not key:
            continue
        if key in keepers:
            duplicates.append((j, keepers[key]))
        else:
            keepers[key] = j

    if not duplicates:
        return

    for loser, survivor in duplicates:
        # Re-point all journal pubs from `loser` to `survivor`. Done as
        # a bulk UPDATE — no per-row work in Python.
        JournalPub.objects.filter(journal=loser).update(journal=survivor)
        loser.delete()


def noop_reverse(apps, schema_editor):
    """Reverse of merge_duplicate_journals.

    The merge is destructive — losing rows are deleted and the original
    pk identities are gone. Re-creating them on rollback would require
    a ``legacy_id`` column the model doesn't have, so the reverse step
    is a no-op. Restoring duplicates from a pre-migration backup is the
    only honest reversal.
    """
    return


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0006_item_doi_link_charfield"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_journals, noop_reverse),
        migrations.AddConstraint(
            model_name="journal",
            constraint=models.UniqueConstraint(
                Lower("name"),
                name="unique_journal_name_case_insensitive",
            ),
        ),
    ]
