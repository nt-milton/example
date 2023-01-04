# Generated by Django 3.1.12 on 2021-09-27 21:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('alert', '0012_add_fieldwork_comment_alert_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='alert',
            name='type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('POST', 'POST'),
                    ('MENTION', 'MENTION'),
                    ('REPLY', 'REPLY'),
                    ('RESOLVE', 'RESOLVE'),
                    ('UNRESOLVE', 'UNRESOLVE'),
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
                ],
                max_length=50,
            ),
        ),
    ]
