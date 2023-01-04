# Generated by Django 3.1.2 on 2021-03-23 18:22

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('evidence', '0022_create_language_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='IgnoreWord',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('word', models.FileField(blank=False, max_length=512, null=False)),
                (
                    'language',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='language',
                        to='evidence.Language',
                    ),
                ),
            ],
        ),
    ]
