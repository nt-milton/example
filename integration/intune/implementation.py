from integration.account import get_integration_laika_objects, integrate_account
from integration.exceptions import ConfigurationError
from integration.integration_utils import token_utils
from integration.intune.mapper import map_managed_devices_response
from integration.intune.rest_client import create_refresh_token, get_managed_devices
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from objects.system_types import DEVICE

MICROSOFT_INTUNE = 'Microsoft Intune'

N_RECORDS = get_integration_laika_objects(MICROSOFT_INTUNE)


def _map_device_response_to_laika_object(response, connection_name):
    return map_managed_devices_response(response, connection_name, MICROSOFT_INTUNE)


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    response = create_refresh_token(code, redirect_uri)
    connection_account.authentication = response
    connection_account.save()
    return connection_account


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        integrate_managed_devices(connection_account=connection_account)
        integrate_account(
            connection_account,
            MICROSOFT_INTUNE,
            N_RECORDS,
        )


def integrate_managed_devices(connection_account: ConnectionAccount):
    token = token_utils.get_access_token(connection_account)
    devices = get_managed_devices(token)
    user_mapper = Mapper(
        map_function=_map_device_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=DEVICE,
    )
    update_laika_objects(connection_account, user_mapper, devices)
