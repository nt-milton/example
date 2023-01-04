from django.db import migrations

from objects.migrate import migrate_lo
from objects.system_types import ACCOUNT


def add_new_columns(apps, schema_editor):
    new_attributes = ['Number of Records']
    migrate_lo(ACCOUNT, new=new_attributes)


class Migration(migrations.Migration):
    dependencies = [
        ('objects', '0030_add_applications_user_field'),
        ('organization', '0048_organization_target_audit_date'),
    ]

    operations = [
        migrations.RunPython(add_new_columns),
    ]
