from django.db import migrations

from objects.migrate import AttributeMerge, AttributeRename, migrate_lo
from objects.system_types import PULL_REQUEST


def migrate_data(apps, schema_editor):
    migrate_lo(
        PULL_REQUEST,
        merge=[AttributeMerge(source=('Repository', 'Number'), target='Key')],
        new=['Key'],
        rename=[AttributeRename(old='Web Link', new='Url')],
        delete=['Number', 'Is Open'],
    )


class Migration(migrations.Migration):
    dependencies = [('objects', '0017_add_groups_user_field')]

    operations = [migrations.RunPython(migrate_data)]
