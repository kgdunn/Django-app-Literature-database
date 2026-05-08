"""Drop the ``ua_string`` and ``ip_address`` PII columns from PageHit.

Mirrors the v1.3.0 trim done in the sister openmv project. After this
migration, every PageHit row holds only (item, item_pk, datetime,
extra_info), so the table can be retained indefinitely without holding
any user-identifying data. Restore from a pre-Phase-4 backup re-runs
this migration and re-trims any restored PII.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('pagehit', '0002_alter_pagehit_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pagehit',
            name='ua_string',
        ),
        migrations.RemoveField(
            model_name='pagehit',
            name='ip_address',
        ),
    ]
