import logging

from integration.account import get_integration_laika_objects, integrate_account
from integration.azure import rest_client
from integration.azure.constants import (
    INVALID_AZURE_CREDENTIALS,
    INVALID_AZURE_OBJECT_ID,
)
from integration.azure.rest_client import PASSWORD_CREDENTIALS
from integration.azure.utils import (
    DEPLOY,
    EXPIRATION,
    GRAPH,
    OBJECT_ID,
    SETTINGS,
    TEMPLATE_STATE,
    delete_object_template,
    get_is_admin_and_role_names,
    get_role_from_definition,
    upload_custom_role_template,
    validate_or_encrypt_value,
)
from integration.encryption_utils import decrypt_value
from integration.exceptions import ConnectionAlreadyExists
from integration.integration_utils.microsoft_utils import (
    MicrosoftRequest,
    ServicePrincipal,
)
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from integration.utils import resolve_laika_object_types
from objects.system_types import ACCOUNT, SERVICE_ACCOUNT, USER, ServiceAccount, User

logger = logging.getLogger(__name__)

AZURE_SYSTEM = 'Microsoft Azure'
N_RECORDS = get_integration_laika_objects(AZURE_SYSTEM)


def _map_user_response_to_laika_object(response, connection_name):
    user = response.user
    organization_name = response.organization[0]['displayName']
    roles = response.roles['roles'] if response.roles is not None else {}
    role_names, is_admin = get_is_admin_and_role_names(roles)
    user_id = f'AZURE-{user["id"]}'
    lo_user = User()
    lo_user.id = user_id
    lo_user.first_name = user['givenName']
    lo_user.last_name = user['surname']
    lo_user.email = user['mail']
    lo_user.title = user.get('jobTitle', '')
    lo_user.is_admin = is_admin
    lo_user.mfa_enabled = ''
    lo_user.roles = ', '.join(sorted(role_names))
    lo_user.mfa_enforced = ''
    lo_user.organization_name = organization_name
    lo_user.groups = user.get('groups', '')
    lo_user.connection_name = connection_name
    lo_user.source_system = AZURE_SYSTEM
    return lo_user.data()


def _map_service_account_response_to_laika_object(response, connection_name):
    service = response.service
    subscription_id = response.subscription
    roles = response.roles['roles'] if response.roles is not None else []
    role_names, _ = get_is_admin_and_role_names(roles=roles)
    lo_service_account = ServiceAccount()
    lo_service_account.id = service['id']
    lo_service_account.display_name = service['displayName']
    lo_service_account.description = service['description']
    lo_service_account.owner_id = subscription_id
    lo_service_account.email = ''
    lo_service_account.created_date = service['createdDateTime']
    lo_service_account.is_active = service['accountEnabled']
    lo_service_account.roles = ', '.join(sorted(role_names))
    lo_service_account.connection_name = connection_name
    lo_service_account.source_system = AZURE_SYSTEM
    return lo_service_account.data()


def run(connection_account):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        validate_or_encrypt_value(connection_account)
        graph_access_token, user_roles = get_common_services(connection_account)
        organization = connection_account.organization
        resolve_laika_object_types(organization, [ACCOUNT, USER, SERVICE_ACCOUNT])
        integrate_users(connection_account, graph_access_token, user_roles)
        integrate_service_accounts(connection_account, graph_access_token, user_roles)
        integrate_account(connection_account, AZURE_SYSTEM, N_RECORDS)


def connect(connection_account):
    configuration_state = connection_account.configuration_state
    if 'credentials' in configuration_state:
        del configuration_state['credentials']['updating']
        validate_or_encrypt_value(connection_account)
        validate_credentials(connection_account)
        process_azure_template(configuration_state, connection_account)


def process_azure_template(configuration_state, connection_account):
    credentials = configuration_state['credentials']
    settings = configuration_state.get(SETTINGS)
    if TEMPLATE_STATE in settings and OBJECT_ID in credentials:
        template_state = configuration_state[SETTINGS][TEMPLATE_STATE]
        if template_state['state'] == DEPLOY:
            upload_custom_role_template(connection_account)


def validate_credentials(connection_account):
    credentials = connection_account.configuration_state.get('credentials')
    with connection_account.connection_error(error_code=INVALID_AZURE_CREDENTIALS):
        response = rest_client.get_access_token(credentials, GRAPH)
        secret_expiration = _read_secret_expiration(
            credentials, response['access_token']
        )

    with connection_account.connection_error(error_code=INVALID_AZURE_OBJECT_ID):
        rest_client.get_service_principal_by_app(
            response['access_token'],
            connection_account.configuration_state['credentials'],
        )

    connection_account.configuration_state[SETTINGS][EXPIRATION] = secret_expiration
    connection_account.authentication = response


def integrate_users(
    connection_account: ConnectionAccount, graph_token: str, user_roles: list
):
    organization = rest_client.get_organization(graph_token)
    users = _read_subscription_users(organization, graph_token, user_roles)
    user_mapper = Mapper(
        map_function=_map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    update_laika_objects(connection_account, user_mapper, users)


def integrate_service_accounts(connection_account, graph_token, user_roles):
    credentials = connection_account.configuration_state.get('credentials')
    subscription_id = credentials['subscriptionId']
    service_principals = _read_subscription_service_principals(
        graph_token, user_roles, subscription_id
    )
    service_account_mapper = Mapper(
        map_function=_map_service_account_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=SERVICE_ACCOUNT,
    )
    update_laika_objects(connection_account, service_account_mapper, service_principals)


def get_common_services(connection_account: ConnectionAccount):
    credentials = connection_account.configuration_state.get('credentials')
    graph_access_token_response = rest_client.get_access_token(credentials, GRAPH)
    graph_access_token = graph_access_token_response['access_token']
    azure_access_token_response = rest_client.get_access_token(credentials)
    azure_access_token = azure_access_token_response['access_token']
    subscription_id = credentials['subscriptionId']
    subscription_users = _read_subscription_role_users(
        azure_access_token, subscription_id
    )
    role_definitions = _read_role_definitions(azure_access_token, subscription_id)
    user_roles, user_ids = get_users_by_role(
        role_definitions, subscription_id, subscription_users
    )
    groups_user_roles = concat_user_roles(user_ids, user_roles)
    return graph_access_token, groups_user_roles


def concat_user_roles(user_ids, user_roles):
    groups_user_roles = []
    for user_id in user_ids:
        roles = list()
        for role in user_roles:
            if role['id'] == user_id:
                roles.append(role)

        groups_user_roles.append(dict(id=user_id, roles=roles))

    return groups_user_roles


def get_users_by_role(role_definitions, subscription_id, subscription_users):
    user_roles = list()
    user_ids = list()
    for user in subscription_users:
        user_ids.append(user['properties']['principalId'])
        user_by_role = filter_roles(role_definitions, user, subscription_id)
        if user_by_role:
            user_roles.append(user_by_role)
    return user_roles, user_ids


def _read_role_definitions(azure_token, subscription_id):
    return rest_client.get_role_definitions(azure_token, subscription_id)


def _read_subscription_users(organization, graph_token, user_roles):
    users = rest_client.get_users_filtered(graph_token, user_roles)

    for role, user in users:
        yield MicrosoftRequest(None, user, organization, role)


def cleanup_connection(key):
    delete_object_template(key)


def _read_subscription_role_users(access_token, subscription_id):
    users = rest_client.get_users_from_subscription_role(access_token, subscription_id)
    for user in users:
        yield user


def _read_subscription_service_principals(
    access_token: str,
    roles: list,
    subscription_id: str,
):
    service_principals = rest_client.get_service_principals(access_token, roles)
    for role, service_principal in service_principals:
        yield ServicePrincipal(service_principal, role, subscription_id)


def _read_secret_expiration(credentials, token):
    client_secret = decrypt_value(credentials.get('clientSecret'))
    hint = client_secret[0:3]
    response = rest_client.get_application_secret_expiration(token, credentials)
    application = response['value'][0]
    secrets = application.get(PASSWORD_CREDENTIALS)
    for secret in secrets:
        if hint == secret.get('hint'):
            return _map_secret_expiration(secret)


def filter_roles(role_definitions, user, subscription_id):
    for role in role_definitions:
        truncate_role: str = user['properties']['roleDefinitionId']
        truncated_role = truncate_role.replace(
            get_role_from_definition(subscription_id), ''
        )
        if truncated_role == role['name']:
            return {
                'id': user['properties']['principalId'],
                'roleName': role['properties']['roleName'],
                'permissions': role['properties']['permissions'][0]['actions'],
                'roleType': role['properties']['type'],
            }


def raise_if_duplicate(connection_account):
    credentials = connection_account.configuration_state.get('credentials')
    subscription_id = credentials.get('subscriptionId')
    exists = (
        ConnectionAccount.objects.actives(
            configuration_state__credentials__subscriptionId=subscription_id,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def _map_secret_expiration(secret):
    return {
        'appName': secret.get('displayName'),
        "endDateTime": secret.get('endDateTime'),
        "startDateTime": secret.get('startDateTime'),
    }
