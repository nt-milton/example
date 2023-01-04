import logging
import re

from django.db import migrations

logger = logging.getLogger(__name__)

G_SUITE = 'G Suite'
GOOGLE_WORKSPACE = 'Google Workspace'


def migrate_g_suite_to_google_workspace(apps, schema_editor):
    connection_account_app = apps.get_model('integration', 'ConnectionAccount')
    integration_app = apps.get_model('integration', 'Integration')
    vendor_app = apps.get_model('vendor', 'Vendor')

    if not vendor_app.objects.filter(name=GOOGLE_WORKSPACE).exists():
        vendor_app.objects.create(name=GOOGLE_WORKSPACE)
        logger.info(f'Vendor Google Workspace created.')

    if not integration_app.objects.filter(vendor__name=GOOGLE_WORKSPACE).exists():
        integration_app.objects.create(
            vendor=vendor_app.objects.get(name=GOOGLE_WORKSPACE)
        )
        logger.info(f'Integration Google Workspace created.')

    google_workspace_integration = integration_app.objects.get(
        vendor__name=GOOGLE_WORKSPACE
    )
    google_workspace_integration.vendor = vendor_app.objects.get(name=GOOGLE_WORKSPACE)

    g_suite_connections = connection_account_app.objects.filter(
        integration__vendor__name=G_SUITE
    )
    logger.info(f'Updating {g_suite_connections.count()} G Suite integrations')
    for g_suite_connection in g_suite_connections.all():
        if 'g suite' in g_suite_connection.alias.lower():
            new_alias = re.sub(
                G_SUITE, GOOGLE_WORKSPACE, g_suite_connection.alias, flags=re.IGNORECASE
            )
            g_suite_connection.alias = new_alias
        g_suite_connection.integration = google_workspace_integration
        g_suite_connection.save()

        logger.info(
            f'Connection account {g_suite_connection.alias} with id '
            f'{g_suite_connection.id} in '
            f'organization {g_suite_connection.organization} was '
            'updated to Google Workspace'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0035_add_timeout_error'),
    ]

    operations = [migrations.RunPython(migrate_g_suite_to_google_workspace)]
