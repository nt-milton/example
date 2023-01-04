import logging

from cryptography.fernet import InvalidToken
from django.db import migrations

from integration.encryption_utils import decrypt_value

logger = logging.getLogger(__name__)


def decrypt_organization_names(apps, _):
    integration_model = apps.get_model('integration', 'Integration')

    integration = integration_model.objects.filter(
        vendor__name__iexact='Github Apps'
    ).first()

    if integration:
        for connection in integration.connection_accounts.all():
            _decrypt_organization(connection)
            _copy_installation_id(connection)
    else:
        logger.info(f'The integration called Github Apps not exist to add alerts')


def _copy_installation_id(connection):
    installation_id = connection.authentication.get('installation', {}).get(
        'installation_id'
    )
    if installation_id:
        connection.configuration_state['credentials'][
            'installation_id'
        ] = installation_id
        connection.save()


def _decrypt_organization(connection):
    value = connection.configuration_state.get('credentials', {}).get('organization')
    if value:
        try:
            decrypted_value = decrypt_value(value)
            connection.configuration_state['credentials'][
                'organization'
            ] = decrypted_value
        except InvalidToken:
            connection.configuration_state['credentials']['organization'] = value
        connection.save()


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0067_add_integration_alerts_for_auth0'),
    ]

    operations = [migrations.RunPython(decrypt_organization_names)]
