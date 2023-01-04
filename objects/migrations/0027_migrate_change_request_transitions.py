from django.db import migrations

from objects.migrate import migrate_lo
from objects.system_types import CHANGE_REQUEST


def migrate_data(apps, schema_editor):
    migrate_lo(
        CHANGE_REQUEST,
        new=['Transitions History'],
        delete=['Transitions'],
        reorder=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0024_adding_values_to_sfdc_field'),
        ('objects', '0026_adding_new_field_to_attribute_model'),
    ]

    operations = [migrations.RunPython(migrate_data)]
