from django.db import migrations

from objects.migrate import migrate_lo
from objects.system_types import CHANGE_REQUEST


def migrate_data(apps, schema_editor):
    migrate_lo(
        CHANGE_REQUEST,
        new=['Title', 'Description', 'Issue Type', 'Epic', 'Url'],
        reorder=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0011_setting_permissions_to_roles'),
        ('objects', '0021_adding_connection_and_source_to_repository_lo'),
    ]

    operations = [migrations.RunPython(migrate_data)]
