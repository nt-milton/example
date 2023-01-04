# Generated by Django 3.1.12 on 2021-12-07 22:43

from django.db import migrations

from integration import error_codes


def adding_reason_errors(apps, schema_editor):
    ErrorCatalogue = apps.get_model('integration', 'ErrorCatalogue')
    Integration = apps.get_model('integration', 'Integration')
    error = ErrorCatalogue.objects.get(code=error_codes.OTHER)
    regex = 'The app is not installed on this instance.'
    title = 'Possible Errors:'
    html = f'<p><strong>{title}</strong></p>\r\n<p>{regex}</p>'
    integration = Integration.objects.filter(vendor__name='Jira').first()
    if integration:
        integration.alerts.update_or_create(
            error=error,
            error_response_regex=regex,
            defaults={'error_message': html},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0040_add_send_email_error_catalogue'),
    ]

    operations = [migrations.RunPython(adding_reason_errors)]
