# Generated by Django 3.1.12 on 2022-01-07 17:40

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('certification', '0008_unique_together_section_name_and_certification'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='certification',
            options={
                'permissions': [
                    ('view_certification_readiness', 'Can view certification readiness')
                ]
            },
        ),
    ]
