import logging
import re

from integration.account import get_integration_laika_objects, integrate_account
from integration.encryption_utils import encrypt_value, get_decrypted_or_encrypted_value
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.log_utils import connection_data
from integration.models import ConnectionAccount
from integration.okta import rest_client
from integration.okta.constants import INVALID_OKTA_API_KEY, INVALID_OKTA_SUBDOMAIN
from integration.okta.utils import (
    OKTA_SYSTEM,
    SIMPLE_DOMAIN_REGEX,
    SUB_DOMAIN_REGEX,
    OktaRequest,
)
from integration.store import Mapper, update_laika_objects
from objects.system_types import USER, User

N_RECORDS = get_integration_laika_objects(OKTA_SYSTEM)

logger = logging.getLogger(__name__)


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        get_decrypted_or_encrypted_value('apiToken', connection_account)
        raise_if_duplicate(connection_account)
        integrate_users(connection_account)
        integrate_account(connection_account, OKTA_SYSTEM, N_RECORDS)


def _map_user_response_to_laika_object(response, connection_name):
    user = response.user
    apps = [app.get('label') for app in response.applications]
    groups = (
        response.groups
        if response.groups == []
        else [group['profile']['name'] for group in response.groups]
    )
    lo_user = User()
    lo_user.id = user['id']
    lo_user.first_name = user.get('profile').get('firstName')
    lo_user.last_name = user.get('profile').get('lastName')
    lo_user.email = user.get('profile').get('email')
    lo_user.title = user.get('profile').get('title')
    lo_user.organization_name = user.get('profile').get('organization')
    lo_user.is_admin = ''
    lo_user.groups = ', '.join(sorted(groups))
    lo_user.applications = ', '.join(sorted(apps))
    lo_user.roles = ''
    lo_user.connection_name = connection_name
    lo_user.mfa_enabled = True if response.factors else False
    lo_user.mfa_enforced = ''
    lo_user.source_system = OKTA_SYSTEM
    return lo_user.data()


def connect(connection_account: ConnectionAccount):
    with connection_account.connection_error():
        if 'credentials' in connection_account.configuration_state:
            connection_account.credentials['apiToken'] = encrypt_value(
                connection_account.credentials.get('apiToken', '')
            )
            connection_account.save()
            validate_credentials(connection_account)


def integrate_users(connection_account: ConnectionAccount):
    user_mapper = Mapper(
        map_function=_map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    users = get_users(connection_account)
    update_laika_objects(connection_account, user_mapper, users)


def validate_credentials(connection_account: ConnectionAccount):
    credentials = get_credentials(connection_account)
    with connection_account.connection_error(error_code=INVALID_OKTA_SUBDOMAIN):
        domain = get_valid_okta_domain(credentials.get('subdomain'))
        credentials['subdomain'] = domain
        connection_account.save()
    with connection_account.connection_error(error_code=INVALID_OKTA_API_KEY):
        rest_client.get_groups(credentials)


def get_users(connection_account: ConnectionAccount):
    data = connection_data(connection_account)
    credentials = get_credentials(connection_account)
    users = rest_client.get_okta_users(credentials, **data)
    for user in users:
        user_id = user.get('id')
        apps = rest_client.get_users_by_segment(
            credentials, user_id, 'appLinks', **data
        )
        groups = rest_client.get_users_by_segment(
            credentials, user_id, 'groups', **data
        )
        factors = rest_client.get_users_by_segment(
            credentials, user_id, 'factors', **data
        )
        yield OktaRequest(user, groups, apps, factors)


def raise_if_duplicate(connection_account: ConnectionAccount):
    credentials = get_credentials(connection_account)
    subdomain = credentials.get('subdomain')
    exists = (
        ConnectionAccount.objects.actives(
            configuration_state__credentials__subdomain=subdomain,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def get_credentials(connection_account: ConnectionAccount):
    return connection_account.configuration_state.get('credentials')


def get_valid_okta_domain(sub_domain: str) -> str:
    if re.match(SIMPLE_DOMAIN_REGEX, sub_domain):
        return f'{sub_domain}.okta.com'

    invalid_subdomain = re.search(SUB_DOMAIN_REGEX, sub_domain)

    if not invalid_subdomain:
        error = {'message': 'subdomain does not match with the valid format'}
        raise ConfigurationError.bad_client_credentials(error)

    return invalid_subdomain.string[invalid_subdomain.start() : invalid_subdomain.end()]
