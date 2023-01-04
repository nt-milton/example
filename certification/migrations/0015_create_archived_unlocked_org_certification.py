# Generated by Django 3.2.13 on 2022-06-06 20:08

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0071_alter_organization_name'),
        ('certification', '0014_set_airtable_record_id_null'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArchivedUnlockedOrganizationCertification',
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
                (
                    'certification',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='archived_unlocked_organizations',
                        to='certification.certification',
                    ),
                ),
                (
                    'organization',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='archived_unlocked_certifications',
                        to='organization.organization',
                    ),
                ),
            ],
        ),
    ]
