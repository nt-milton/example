# Generated by Django 3.1.12 on 2021-11-18 17:03
from django.db import migrations, models

from integration import error_codes

ERROR_VALUES = [
    (error_codes.NONE, 'None'),
    (error_codes.OTHER, 'Other'),
    (error_codes.INSUFFICIENT_PERMISSIONS, 'Insufficient Permissions'),
    (error_codes.MISSING_GITHUB_ORGANIZATION, 'Missing Github Organization'),
    (error_codes.DENIAL_OF_CONSENT, 'Denial Of Consent'),
    (error_codes.INSUFFICIENT_CONFIG_DATA, 'Insufficient Config Data'),
    (error_codes.BAD_CLIENT_CREDENTIALS, 'Invalid Client Credentials'),
    (error_codes.EXPIRED_TOKEN, 'Expired Token'),
    (error_codes.PROVIDER_SERVER_ERROR, 'Provider Server Error'),
    (error_codes.RESOURCE_NOT_FOUND, 'Resource Not Found'),
    (error_codes.API_LIMIT, 'API Limit Exceeded'),
    (error_codes.MISSING_GITHUB_APP_INSTALLATION, 'Missing Github App'),
    (error_codes.PROVIDER_GRAPHQL_ERROR, 'Provider Graphql API Error'),
    (error_codes.CONNECTION_TIMEOUT, 'Connection Time Out'),
    (error_codes.DEFAULT_GRAPHQL_ERROR, 'Default GraphQL Error'),
]


def adding_reason_errors(apps, schema_editor):
    error_catalogue_model = apps.get_model('integration', 'ErrorCatalogue')
    for error in ERROR_VALUES:
        code, reason = error
        error_updated, _ = error_catalogue_model.objects.update_or_create(
            code=code, defaults={'failure_reason_mail': reason}
        )


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0037_add_integration_error_catalogue'),
    ]

    operations = [
        migrations.AddField(
            model_name='errorcatalogue',
            name='failure_reason_mail',
            field=models.CharField(default='', max_length=100),
        ),
        migrations.RunPython(adding_reason_errors),
    ]
