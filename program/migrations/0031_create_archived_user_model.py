# Generated by Django 3.1.2 on 2021-01-22 00:18

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('program', '0030_create_archived_program_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArchivedUser',
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
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('first_name', models.CharField(blank=True, max_length=150, null=True)),
                ('last_name', models.CharField(blank=True, max_length=150, null=True)),
                ('email', models.CharField(max_length=150)),
            ],
            options={
                'verbose_name_plural': 'archived users',
            },
        ),
        migrations.AddField(
            model_name='archivedevidence',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='archived_evidence',
                to='program.archiveduser',
            ),
        ),
    ]
