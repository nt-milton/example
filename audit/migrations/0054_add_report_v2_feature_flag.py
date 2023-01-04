# Generated by Django 3.2.15 on 2022-09-13 16:59

from django.db import migrations


def add_draft_report_v2_feature_flag(apps, schema_editor):
    audit_firm_model = apps.get_model('audit', 'AuditFirm')
    flag_model = apps.get_model('feature', 'AuditorFlag')

    for audit_firm in audit_firm_model.objects.all():
        flag_model.objects.get_or_create(
            name='draftReportV2FeatureFlag',
            audit_firm=audit_firm,
            defaults={'is_enabled': False},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0053_add_field_section_report_section_framework_template'),
    ]

    operations = [migrations.RunPython(add_draft_report_v2_feature_flag)]
