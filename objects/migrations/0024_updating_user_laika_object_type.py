from django.db import migrations

from objects.migrate import AttributeMerge, AttributeRename, migrate_lo
from objects.system_types import USER


def migrate_data(apps, schema_editor):
    migrate_lo(
        USER, new=['Roles', 'Groups'], delete=['Is Delegated Admin'], reorder=True
    )


class Migration(migrations.Migration):
    dependencies = [('objects', '0023_adding_configurations_field_in_account')]

    operations = [migrations.RunPython(migrate_data)]
