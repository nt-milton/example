# Generated by Django 3.1.6 on 2021-06-22 22:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('alert', '0010_new_training_remainder_type'),
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
                ],
                max_length=50,
            ),
        ),
    ]
