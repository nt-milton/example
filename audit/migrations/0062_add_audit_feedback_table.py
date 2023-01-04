# Generated by Django 3.2.15 on 2022-11-21 21:09

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0061_add_audit_feedback_reason_table'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditFeedback',
            fields=[
                (
                    'audit',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name='audit_feedback',
                        serialize=False,
                        to='audit.audit',
                    ),
                ),
                ('rate', models.DecimalField(decimal_places=1, max_digits=2)),
                ('feedback', models.TextField(blank=True)),
                ('reason', models.JSONField()),
            ],
        ),
    ]
