# Generated by Django 3.1.2 on 2020-12-03 17:50

from django.db import migrations

from objects.migrate import migrate_lo
from objects.system_types import CHANGE_REQUEST, PULL_REQUEST, USER


def add_new_columns(apps, schema_editor):
    new_attributes = ['Source System', 'Connection Name']
    migrate_lo(PULL_REQUEST, new=new_attributes)
    migrate_lo(CHANGE_REQUEST, new=new_attributes)
    migrate_lo(USER, new=new_attributes)


class Migration(migrations.Migration):
    dependencies = [
        ('objects', '0013_consolidate_system_names'),
    ]

    operations = [
        migrations.RunPython(add_new_columns),
    ]
