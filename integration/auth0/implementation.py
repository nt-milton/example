from integration.account import integrate_account
from integration.auth0.constants import (
    AUTH0_SYSTEM,
    INSUFFICIENT_PERMISSIONS,
    N_RECORDS,
    REQUIRED_SCOPES,
)
from integration.auth0.mapper import map_user_builder
from integration.auth0.rest_client import get_token, get_users
from integration.encryption_utils import encrypt_value
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from objects.system_types import USER


def integrate_users(connection_account):
    users = get_users(connection_account)
    user_mapper = Mapper(
        map_function=map_user_builder(connection_account),
        keys=['Id'],
        laika_object_spec=USER,
    )
    update_laika_objects(connection_account, user_mapper, users)


def verify_scopes(scopes):
    required_scopes = set(REQUIRED_SCOPES.split())
    if not required_scopes.issubset(set(scopes.split())):
        raise ConfigurationError.insufficient_permission()


def connect(connection_account: ConnectionAccount):
    with connection_account.connection_error():
        if 'credentials' in connection_account.configuration_state:
            with connection_account.connection_error(INSUFFICIENT_PERMISSIONS):
                response = get_token(connection_account)
                verify_scopes(response.get('scope'))


def raise_if_duplicate(connection_account: ConnectionAccount):
    identifier = connection_account.credentials.get('identifier')
    exists = (
        ConnectionAccount.objects.actives(
            configuration_state__credentials__identifier=identifier,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def run(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        response = get_token(connection_account)
        connection_account.authentication['access_token'] = encrypt_value(
            response.get('access_token')
        )
        connection_account.save()
        integrate_users(connection_account)
        integrate_account(connection_account, AUTH0_SYSTEM, N_RECORDS)
