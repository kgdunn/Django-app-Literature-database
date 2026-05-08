"""Install the `pg_trgm` extension that powers `__trigram_similar` lookups
on author last names in `pages.search`.

Phase 3 made Postgres the only supported backend (both dev and prod
settings point at it), so this migration always runs the `CREATE
EXTENSION` body. `TrigramExtension` does still no-op on non-Postgres
backends, which keeps the migration history valid against any future
backend swap.
"""

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('items', '0003_alter_author_id_alter_authorgroup_id_alter_item_id_and_more'),
    ]

    operations = [
        TrigramExtension(),
    ]
