import logging

from integration.account import get_integration_laika_objects, integrate_account
from integration.digitalocean.constants import DIGITALOCEAN, INVALID_TOKEN
from integration.digitalocean.mapper import map_alert_policy_to_monitor_lo
from integration.digitalocean.rest_client import (
    get_alert_policies,
    get_paginated_alert_policies,
)
from integration.encryption_utils import get_decrypted_or_encrypted_value
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from objects.system_types import MONITOR

logger = logging.getLogger(__name__)
N_RECORDS = get_integration_laika_objects(DIGITALOCEAN)


def get_access_token(connection_account: ConnectionAccount) -> str:
    return get_decrypted_or_encrypted_value('accessToken', connection_account)


def connect(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_error(error_code=INVALID_TOKEN):
        access_token = get_access_token(connection_account)
        response = get_alert_policies(access_token, 1)
        if not response.ok:
            raise ConfigurationError.bad_client_credentials(response=response)


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        access_token = get_access_token(connection_account)
        integrate_monitors(
            connection_account=connection_account, access_token=access_token
        )
        integrate_account(connection_account, DIGITALOCEAN, N_RECORDS)


def integrate_monitors(connection_account: ConnectionAccount, access_token: str):
    monitors = get_paginated_alert_policies(access_token)
    users_mapper = Mapper(
        map_function=map_alert_policy_to_monitor_lo,
        keys=['Id'],
        laika_object_spec=MONITOR,
    )
    update_laika_objects(
        connection_account=connection_account, mapper=users_mapper, raw_objects=monitors
    )


def raise_if_duplicate(connection_account: ConnectionAccount):
    access_token = get_access_token(connection_account)
    connection_accounts = ConnectionAccount.objects.filter(
        organization=connection_account.organization,
        integration=connection_account.integration,
    ).exclude(id=connection_account.id)
    for current_connection_account in connection_accounts:
        decrypted_access_token = get_decrypted_or_encrypted_value(
            'accessToken', current_connection_account
        )
        if access_token == decrypted_access_token:
            raise ConnectionAlreadyExists()
