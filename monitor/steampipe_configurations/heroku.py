from integration.encryption_utils import decrypt_value
from integration.models import ConnectionAccount
from monitor.steampipe_configurations.constants import NO_CACHE


def get_heroku_configuration(profile_name: str, connection: ConnectionAccount) -> str:
    credentials = connection.credentials
    api_key = decrypt_value(credentials['apiKey'])
    email = credentials['email']

    return (
        f'connection "{profile_name}" {{\n'
        '  plugin    = "heroku"\n'
        f' email   = "{email}"\n'
        f' api_key = "{api_key}"\n'
        f'{NO_CACHE}'
        '}'
    )
