from django.db import migrations


class Migration(migrations.Migration):
    """v1.1.0: drop the legacy ``Item.show_abstract`` gate.

    The 2010-era schema kept abstracts hidden behind an admin opt-in
    boolean that defaulted to False. The revived site has no review
    workflow that would flip it, so it became a permanent suppressor
    for every abstract on the site. The detail-page template now
    gates on ``Item.abstract`` content directly; this migration
    removes the now-vestigial column.
    """

    dependencies = [
        ("items", "0009_item_pdf_file_extension_validator"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="item",
            name="show_abstract",
        ),
    ]
