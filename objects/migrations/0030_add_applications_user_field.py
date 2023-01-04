from django.db import migrations

from objects.migrate import migrate_lo
from objects.system_types import USER


def add_new_columns(apps, schema_editor):
    new_attributes = ['Applications']
    migrate_lo(USER, new=new_attributes)


class Migration(migrations.Migration):
    dependencies = [
        ('objects', '0029_update_owners_in_accounts'),
        ('organization', '0046_organization_is_internal'),
    ]

    operations = [
        migrations.RunPython(add_new_columns),
    ]
