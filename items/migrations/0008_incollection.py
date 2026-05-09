"""Issue #14 / #31: ``InCollection`` book-chapter subclass.

Adds the ``incollection`` choice to ``Item.item_type`` and creates the
``items_incollection`` table with a OneToOne back to ``Item``
(multi-table inheritance, mirroring JournalPub / Book /
ConferenceProceeding / Thesis).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0007_unique_journal_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="item_type",
            field=models.CharField(
                choices=[
                    ("thesis", "Thesis"),
                    ("journalpub", "Journal publication"),
                    ("book", "Book"),
                    ("conferenceproc", "Conference proceeding"),
                    ("incollection", "Book chapter"),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="InCollection",
            fields=[
                (
                    "item_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="items.item",
                    ),
                ),
                (
                    "book_title",
                    models.CharField(
                        help_text="Title of the book containing this chapter.",
                        max_length=510,
                    ),
                ),
                (
                    "edition",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "isbn",
                    models.CharField(
                        blank=True, max_length=20, null=True, verbose_name="ISBN"
                    ),
                ),
                (
                    "page_start",
                    models.CharField(blank=True, max_length=10, null=True),
                ),
                (
                    "page_end",
                    models.CharField(blank=True, max_length=10, null=True),
                ),
                ("editors", models.ManyToManyField(blank=True, to="items.author")),
                (
                    "publisher",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="items.publisher",
                    ),
                ),
            ],
            options={
                "verbose_name": "book chapter",
                "verbose_name_plural": "book chapters",
            },
            bases=("items.item",),
        ),
    ]
