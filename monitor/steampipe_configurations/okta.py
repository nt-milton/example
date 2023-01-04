import re

from integration.models import ConnectionAccount
from monitor.steampipe_configurations.constants import NO_CACHE


def format_subdomain(subdomain):
    formatted_subdomain = subdomain
    if not re.match(r'https?://', subdomain):
        formatted_subdomain = f'https://{formatted_subdomain}'
    if '-admin' in subdomain:
        formatted_subdomain = formatted_subdomain.replace('-admin', '')
    return formatted_subdomain


def get_okta_configuration(profile_name: str, connection: ConnectionAccount) -> str:
    configuration_state = connection.configuration_state
    api_token = configuration_state['credentials']['apiToken']
    subdomain = format_subdomain(configuration_state['credentials']['subdomain'])

    return (
        f'connection "{profile_name}" {{\n'
        '  plugin    = "okta"\n'
        f' domain   = "{subdomain}"\n'
        f' token = "{api_token}"\n'
        f'{NO_CACHE}'
        '}'
    )
