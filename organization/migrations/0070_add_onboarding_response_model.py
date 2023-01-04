# Generated by Django 3.1.12 on 2022-03-25 13:48

import django.contrib.postgres.indexes
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0069_complete_onboarding_for_missing_orgs'),
    ]

    operations = [
        migrations.CreateModel(
            name='OnboardingResponse',
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
                ('questionary_id', models.CharField(max_length=16)),
                ('response_id', models.CharField(blank=True, max_length=50, null=True)),
                ('questionary_response', models.JSONField(blank=True, null=True)),
                (
                    'organization',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='onboarding_response',
                        to='organization.organization',
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name='onboardingresponse',
            index=django.contrib.postgres.indexes.GinIndex(
                fields=['questionary_response'], name='organizatio_questio_503e58_gin'
            ),
        ),
    ]
