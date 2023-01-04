# Generated by Django 3.0.7 on 2020-09-25 15:40

from django.contrib.auth.management import create_permissions
from django.db import migrations


def create_perms(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


class Migration(migrations.Migration):
    dependencies = [
        ('program', '0020_program_icon_images'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='subtask',
            options={
                'ordering': ('sort_index',),
                'permissions': [
                    ('change_subtask_partial', 'Can change subtask partially')
                ],
            },
        ),
        migrations.AlterModelOptions(
            name='task',
            options={
                'permissions': [
                    (
                        'change_task_implementation_notes',
                        'Can change task implementation notes',
                    )
                ]
            },
        ),
    ]
