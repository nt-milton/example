import time

from integration.aws.aws_client import assume_role_credentials
from integration.models import ConnectionAccount
from monitor.steampipe_configurations.constants import NO_CACHE


def get_aws_configuration(profile_name: str, connection: ConnectionAccount) -> str:
    aws_regions = str(connection.authentication.get('aws_regions')).replace('\'', '"')

    expiration_time = connection.authentication.get('token_expiration_time', 0)
    if time.time() - expiration_time > 0:
        assume_role_credentials(connection)

    aws_access_key = connection.authentication['access_key_id']
    aws_secret_access_key = connection.authentication['secret_access_key']
    aws_session_token = connection.authentication['session_token']
    return (
        f'connection "{profile_name}" {{\n'
        '  plugin    = "aws"\n'
        f'  access_key = "{aws_access_key}"\n'
        f'  secret_key = "{aws_secret_access_key}"\n'
        f'  session_token = "{aws_session_token}"\n'
        f'  regions = {aws_regions}\n'
        f'{NO_CACHE}'
        '}'
    )
