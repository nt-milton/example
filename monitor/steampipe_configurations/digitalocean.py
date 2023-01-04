from integration.encryption_utils import get_decrypted_or_encrypted_value
from integration.models import ConnectionAccount
from monitor.steampipe_configurations.constants import NO_CACHE


def get_digitalocean_configuration(
    profile_name: str, connection: ConnectionAccount
) -> str:
    access_token = get_decrypted_or_encrypted_value('accessToken', connection)
    return (
        f'connection "{profile_name}" {{\n'
        '  plugin    = "digitalocean"\n'
        f' token   = "{access_token}"\n'
        f'{NO_CACHE}'
        '}'
    )
