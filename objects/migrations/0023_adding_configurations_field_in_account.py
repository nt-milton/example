from django.db import migrations

from objects.migrate import migrate_lo
from objects.system_types import ACCOUNT


def migrate_data(app, schema_editor):
    migrate_lo(ACCOUNT, new=['Configurations'], reorder=True)


class Migration(migrations.Migration):
    dependencies = [('objects', '0022_migrate_change_request')]

    operations = [migrations.RunPython(migrate_data)]
