# Generated by Django 3.1.2 on 2021-02-09 19:22

from django.db import migrations

from objects.migrate import migrate_lo
from objects.system_types import REPOSITORY


def add_new_columns(apps, schema_editor):
    new_attributes = ['Source System', 'Connection Name']
    migrate_lo(REPOSITORY, new=new_attributes)


class Migration(migrations.Migration):
    dependencies = [
        ('objects', '0020_removing_owner_field_repository_lo'),
    ]

    operations = [
        migrations.RunPython(add_new_columns),
    ]
