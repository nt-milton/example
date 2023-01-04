# Generated by Django 3.2.15 on 2022-09-29 15:10

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('vendor', '0031_very_high_to_critical_risk'),
        ('organization', '0075_onboarding_calendly_v2'),
        ('access_review', '0017_protect_access_review_vendor_on_org_vendor_delete'),
    ]

    operations = [
        migrations.AddField(
            model_name='accessreviewvendorpreference',
            name='organization',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='access_review_vendor_preferences',
                to='organization.organization',
            ),
        ),
        migrations.AddField(
            model_name='accessreviewvendorpreference',
            name='vendor',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='access_review_vendor_preferences',
                to='vendor.vendor',
            ),
        ),
        migrations.RunSQL(
            sql='''
                UPDATE access_review_accessreviewvendorpreference AS arvp 
                SET organization_id = ov.organization_id, vendor_id = ov.vendor_id 
                FROM vendor_organizationvendor AS ov 
                WHERE ov.id = arvp.organization_vendor_id;
            ''',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name='accessreviewvendorpreference',
            name='organization_vendor',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='access_review_vendor_preference',
                to='vendor.organizationvendor',
            ),
        ),
    ]
