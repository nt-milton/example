# Generated by Django 3.0.3 on 2020-04-04 02:41

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('vendor', '0008_vendor_categories_to_many_to_many'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationvendorstakeholder',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='organizationvendorstakeholder',
            name='organization_vendor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='internal_organization_stakeholders',
                to='vendor.OrganizationVendor',
            ),
        ),
    ]
