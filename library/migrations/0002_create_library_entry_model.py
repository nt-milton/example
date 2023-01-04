# Generated by Django 3.0.3 on 2020-06-30 20:14

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

from laika.constants import CATEGORIES, CHOICES


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0006_auto_20200421_1655'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('library', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='libraryentry',
            options={'verbose_name_plural': 'library_entries'},
        ),
        migrations.AddField(
            model_name='libraryentry',
            name='answer_choice',
            field=models.CharField(choices=CHOICES, default='', max_length=10),
        ),
        migrations.AddField(
            model_name='libraryentry',
            name='answer_text',
            field=models.TextField(default=''),
        ),
        migrations.AddField(
            model_name='libraryentry',
            name='category',
            field=models.CharField(choices=CATEGORIES, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='libraryentry',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='libraryentry',
            name='display_id',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='libraryentry',
            name='organization',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='library_entries',
                to='organization.Organization',
            ),
        ),
        migrations.AddField(
            model_name='libraryentry',
            name='updated_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='libraryentry',
            name='updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='user_library_entry',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='Question',
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
                ('text', models.TextField(unique=True)),
                ('default', models.BooleanField()),
                (
                    'library_entry',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='questions',
                        to='library.LibraryEntry',
                    ),
                ),
            ],
            options={
                'verbose_name_plural': 'questions',
            },
        ),
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['text'], name='library_que_text_4325ca_idx'),
        ),
    ]
