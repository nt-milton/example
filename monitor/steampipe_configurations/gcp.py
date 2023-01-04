import json

from integration.integration_utils.google_utils import get_json_credentials
from integration.models import ConnectionAccount
from monitor.steampipe_configurations.constants import NO_CACHE


def get_gcp_configuration(profile_name: str, connection: ConnectionAccount) -> str:
    configuration_state = connection.configuration_state
    credentials = get_json_credentials(connection)
    project_name = configuration_state['project']['projectId']
    file_name = f'gcp-{connection.organization.id}-{connection.control}.json'
    credential_file_path = f'/tmp/{file_name}'
    with open(credential_file_path, 'w') as writer:
        writer.write(json.dumps(credentials))

    return (
        f'connection "{profile_name}" {{\n'
        '  plugin    = "gcp"\n'
        f' project   = "{project_name}"\n'
        f' credential_file = "{credential_file_path}"\n'
        f'{NO_CACHE}'
        '}'
    )
