"""Issue #82: add ``FileExtensionValidator(allowed_extensions=["pdf"])``
to ``Item.pdf_file``.

Validators don't change the underlying SQL column shape — this
migration is metadata-only. Existing rows with non-pdf paths (none in
the current corpus, but defensive) keep their values; the validator
only fires on new uploads via the admin form's ``clean_pdf_file()``
path.
"""

from django.core.validators import FileExtensionValidator
from django.db import migrations, models

import items.models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0008_incollection"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="pdf_file",
            field=models.FileField(
                blank=True,
                max_length=255,
                null=True,
                upload_to=items.models.Item.upload_dest,
                validators=[
                    FileExtensionValidator(allowed_extensions=["pdf"])
                ],
                verbose_name="PDF file (admin-only; not exposed for download)",
            ),
        ),
    ]
