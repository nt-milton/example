# Generated by Django 3.0.7 on 2020-07-27 16:29

from django.contrib.auth.management import create_permissions
from django.db import migrations


def create_perms(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


class Migration(migrations.Migration):
    dependencies = [
        ('library', '0005_removing_unique_question'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='libraryentry',
            options={
                'permissions': [('bulk_upload_library', 'Can bulk upload library')],
                'verbose_name_plural': 'library entries',
            },
        ),
        migrations.RunPython(create_perms),
    ]
