import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def copy_installation_id(apps, _):
    integration_model = apps.get_model('integration', 'Integration')

    integration = integration_model.objects.filter(
        vendor__name__iexact='Github Apps'
    ).first()

    if integration:
        for connection in integration.connection_accounts.all():
            installation_id = connection.authentication.get('installation', {}).get(
                'installation_id'
            )
            if installation_id:
                connection.configuration_state['credentials'][
                    'installationId'
                ] = installation_id
                connection.configuration_state['credentials'].pop(
                    'installation_id', None
                )
                connection.save()
    else:
        logger.info(f'The integration called Github Apps not exist to add alerts')


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0070_add_debug_action_options'),
    ]

    operations = [migrations.RunPython(copy_installation_id)]
