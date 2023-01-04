# Generated by Django 3.1.12 on 2022-02-16 21:04

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0044_add_wizard_known_error_messages'),
    ]

    operations = [
        migrations.AlterField(
            model_name='connectionaccount',
            name='error_code',
            field=models.CharField(
                choices=[
                    ('000', 'None'),
                    ('001', 'Other'),
                    ('002', 'Insufficient Permissions'),
                    ('003', 'Missing Github Organization'),
                    ('004', 'Denial Of Consent'),
                    ('005', 'Insufficient Config Data'),
                    ('006', 'Invalid Client Credentials'),
                    ('007', 'AWS error'),
                    ('008', 'Expired account'),
                    ('009', 'Azure error'),
                    ('010', 'Google Cloud (GCP) error'),
                    ('011', 'Provider Server Error'),
                    ('012', 'Resource not found'),
                    ('013', 'API call exceeded rate limit due to too many requests'),
                    ('014', 'Github App is not installed on the organization'),
                    ('015', 'Provider Graphql API Error'),
                    ('016', 'Connection Time Out'),
                    ('017', 'Default GraphQL Error'),
                    ('018', 'Access Revoked'),
                    ('019', 'The user entered an invalid value'),
                ],
                default='000',
                max_length=20,
            ),
        ),
    ]
