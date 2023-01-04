# Generated by Django 3.1.12 on 2022-01-06 17:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('alert', '0015_add_alert_types_draft_report'),
    ]

    operations = [
        migrations.AlterField(
            model_name='alert',
            name='type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('MENTION', 'MENTION'),
                    ('REPLY', 'REPLY'),
                    ('RESOLVE', 'RESOLVE'),
                    ('NEW_ASSIGNMENT', 'NEW_ASSIGNMENT'),
                    ('ASSIGNMENT_COMPLETED', 'ASSIGNMENT_COMPLETED'),
                    ('AUDIT_REQUESTED', 'AUDIT_REQUESTED'),
                    ('AUDIT_INITIATED', 'AUDIT_INITIATED'),
                    ('DRAFT_REPORT_AVAILABLE', 'DRAFT_REPORT_AVAILABLE'),
                    ('AUDIT_COMPLETE', 'AUDIT_COMPLETE'),
                    ('ORG_REQUESTED_AUDIT', 'ORG_REQUESTED_AUDIT'),
                    ('ORG_COMPLETED_DRAFT_REPORT', 'ORG_COMPLETED_DRAFT_REPORT'),
                    ('ORG_COMPLETED_INITIATION', 'ORG_COMPLETED_INITIATION'),
                    ('VENDOR_DISCOVERY', 'VENDOR_DISCOVERY'),
                    ('PEOPLE_DISCOVERY', 'PEOPLE_DISCOVERY'),
                    ('TRAINING_REMINDER', 'TRAINING_REMINDER'),
                    ('SEEDING_FINISH_REMINDER', 'SEEDING_FINISH_REMINDER'),
                    ('EVIDENCE_MENTION', 'EVIDENCE_MENTION'),
                    ('EVIDENCE_REPLY', 'EVIDENCE_REPLY'),
                    ('REQUIREMENT_REPLY', 'REQUIREMENT_REPLY'),
                    ('REQUIREMENT_MENTION', 'REQUIREMENT_MENTION'),
                    ('ORG_APPROVED_DRAFT_REPORT', 'ORG_APPROVED_DRAFT_REPORT'),
                    ('ORG_SUGGESTED_DRAFT_EDITS', 'ORG_SUGGESTED_DRAFT_EDITS'),
                    (
                        'AUDITOR_PUBLISHED_DRAFT_REPORT',
                        'AUDITOR_PUBLISHED_DRAFT_REPORT',
                    ),
                    ('AUDITEE_DRAFT_REPORT_MENTION', 'AUDITEE_DRAFT_REPORT_MENTION'),
                ],
                max_length=50,
            ),
        ),
    ]
