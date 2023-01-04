# Generated by Django 3.1.2 on 2021-04-14 17:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('alert', '0006_update_alert_choices_auditor_app'),
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
                    ('USER_REQUESTED_AUDIT', 'USER_REQUESTED_AUDIT'),
                    ('USER_COMPLETED_DRAFT_REPORT', 'USER_COMPLETED_DRAFT_REPORT'),
                    ('USER_COMPLETED_INITIATION', 'USER_COMPLETED_INITIATION'),
                    ('VENDOR_DISCOVERY', 'VENDOR_DISCOVERY'),
                ],
                max_length=50,
            ),
        ),
    ]
