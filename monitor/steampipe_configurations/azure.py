from integration.encryption_utils import decrypt_value
from integration.models import ConnectionAccount
from monitor.steampipe_configurations.constants import NO_CACHE


def get_value(connection, key):
    return str(connection.configuration_state.get('credentials', {}).get(key)).replace(
        '\'', '"'
    )


def get_azure_configuration(profile_name: str, connection: ConnectionAccount) -> str:
    subscription_id = get_value(connection, 'subscriptionId')
    client_id = get_value(connection, 'clientId')
    client_secret = decrypt_value(get_value(connection, 'clientSecret'))
    tenant_id = get_value(connection, 'tenantId')

    return (
        f'connection "{profile_name}" {{\n'
        '  plugin    = "azure"\n'
        f' subscription_id = "{subscription_id}"\n'
        f' client_id = "{client_id}"\n'
        f' client_secret = "{client_secret}"\n'
        f' tenant_id = "{tenant_id}"\n'
        f'{NO_CACHE}'
        '}\n'
        f'connection "azuread_{profile_name}" {{\n'
        '  plugin    = "azuread"\n'
        f' client_id = "{client_id}"\n'
        f' client_secret = "{client_secret}"\n'
        f' tenant_id = "{tenant_id}"\n'
        f'{NO_CACHE}'
        '}\n'
    )
