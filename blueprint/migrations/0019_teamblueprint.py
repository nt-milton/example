# Generated by Django 3.1.12 on 2022-04-22 16:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('blueprint', '0018_officer_blueprint_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeamBlueprint',
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
                ('name', models.TextField(max_length=200, unique=True)),
                ('airtable_record_id', models.CharField(blank=True, max_length=512)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField()),
                ('description', models.CharField(blank=True, max_length=2048)),
                ('charter', models.CharField(blank=True, max_length=2048)),
            ],
            options={
                'verbose_name_plural': 'Teams Blueprint',
            },
        ),
    ]
