# Generated by Django 3.1.2 on 2021-01-12 02:03

from django.db import migrations

from drive.sql import TAGS_AND_SYSTEM_TAGS


class Migration(migrations.Migration):
    dependencies = [
        ('drive', '0007_update_tags_and_system_tags'),
    ]

    operations = [migrations.RunSQL(TAGS_AND_SYSTEM_TAGS)]
