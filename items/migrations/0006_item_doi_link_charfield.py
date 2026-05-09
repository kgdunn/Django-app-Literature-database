"""Issue #20: switch ``Item.doi_link`` from URLField to CharField.

The new field uses a custom validator (``validate_doi_or_url``) that
accepts either a full URL OR a bare DOI suffix (``10.1234/foo``);
``Item.save()`` then normalises bare suffixes to the canonical
``https://doi.org/<suffix>`` form.

URLField and CharField both store as ``varchar`` at the Postgres level
with the same max_length (200), so this migration is metadata-only.
No data is rewritten.
"""

from django.db import migrations, models

import items.models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0005_drop_pdf_visibility_flags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="doi_link",
            field=models.CharField(
                blank=True,
                help_text="Full URL or bare DOI (e.g. 10.1234/foo).",
                max_length=200,
                null=True,
                validators=[items.models.validate_doi_or_url],
                verbose_name="DOI link",
            ),
        ),
    ]
