# Generated by Django 3.1.12 on 2022-02-01 23:04

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('control', '0040_control_implementation_date'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='control',
            options={
                'permissions': [
                    ('batch_delete_control', 'Can batch delete controls'),
                    ('change_control_status', 'Can change control status'),
                    ('associate_user', 'Can associate user to control'),
                    ('add_control_evidence', 'Can add control evidence'),
                    ('delete_control_evidence', 'Can delete control evidence'),
                    ('can_migrate_to_my_compliance', 'Can migrate to my compliance'),
                ]
            },
        ),
    ]
