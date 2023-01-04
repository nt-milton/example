# Generated by Django 3.0.3 on 2020-06-03 20:38

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('evidence', '0003_add_additional_evidence_fields'),
        ('vendor', '0010_use_sort_index_for_stakeholders'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizationVendorEvidence',
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
                (
                    'evidence',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='evidence.Evidence',
                    ),
                ),
                (
                    'organization_vendor',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='organization_vendor_evidence',
                        to='vendor.OrganizationVendor',
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='organizationvendor',
            name='documents',
            field=models.ManyToManyField(
                related_name='organization_vendor',
                through='vendor.OrganizationVendorEvidence',
                to='evidence.Evidence',
            ),
        ),
    ]
