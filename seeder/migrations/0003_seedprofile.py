# Generated by Django 3.1.2 on 2021-05-09 17:35

import uuid

from django.db import migrations, models

import laika.storage
import seeder.models


class Migration(migrations.Migration):
    dependencies = [
        ('seeder', '0002_auto_20200421_1655'),
    ]

    operations = [
        migrations.CreateModel(
            name='SeedProfile',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                ('created_at', models.DateField(auto_now_add=True)),
                ('updated_at', models.DateField(auto_now=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, default='')),
                (
                    'file',
                    models.FileField(
                        max_length=512,
                        storage=laika.storage.PrivateMediaStorage(),
                        upload_to=seeder.models.seed_profiles_directory_path,
                    ),
                ),
            ],
        ),
    ]
