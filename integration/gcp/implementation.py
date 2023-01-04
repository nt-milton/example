import itertools
import logging
from typing import Any, Dict, List, Tuple, Union

from integration.store import Mapper, update_laika_objects
from integration.utils import resolve_laika_object_types
from objects.system_types import ACCOUNT, SERVICE_ACCOUNT, USER

from ..account import get_integration_laika_objects, integrate_account
from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..integration_utils.google_utils import (
    convert_base64_to_json,
    get_decrypted_or_encrypt_gcp_file,
    get_json_credentials,
)
from ..models import ConnectionAccount
from ..types import GoogleCloudServicesType
from .constants import GCP_INVALID_FILE
from .mapper import (
    _get_split_member_values,
    map_gcp_project_members_response,
    map_gcp_project_service_accounts_response,
)
from .rest_client import (
    check_iam_permissions,
    get_batch_services_info,
    get_credentials,
    get_credentials_with_scopes,
    get_members_from_project,
    get_project_info,
    get_role_permissions,
    get_service_accounts_from_project,
)

logger = logging.getLogger(__name__)

GCP_SYSTEM = 'Google Cloud Platform (GCP)'
REQUIRED_CREDENTIALS_FIELDS = ['token_uri', 'client_email']
N_RECORDS = get_integration_laika_objects(GCP_SYSTEM)


def perform_refresh_token(connection_account: ConnectionAccount):
    credentials, scopes = get_gcp_credentials(connection_account)
    if not credentials or not scopes:
        logger.warning(
            f'Error getting credentials for {GCP_SYSTEM} '
            f'connection account {connection_account.id}'
        )


def _map_member_response(response, connection_name):
    return map_gcp_project_members_response(response, connection_name, GCP_SYSTEM)


def _map_service_account_response(response, connection_name):
    return map_gcp_project_service_accounts_response(
        response, connection_name, GCP_SYSTEM
    )


def run(connection_account):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        organization = connection_account.organization
        resolve_laika_object_types(organization, [ACCOUNT, USER])
        service_account_members_with_role = integrate_users(connection_account)
        integrate_service_accounts(
            connection_account=connection_account,
            service_account_member_with_role=service_account_members_with_role,
        )
        integrate_account(connection_account, GCP_SYSTEM, N_RECORDS)


def connect(connection_account):
    with connection_account.connection_error(error_code=GCP_INVALID_FILE):
        if 'credentials' in connection_account.configuration_state:
            del connection_account.configuration_state['credentials']['updating']
            json_credentials, scoped_credentials = get_gcp_credentials(
                connection_account
            )
            check_iam_permissions(
                scoped_credentials,
                json_credentials.get('project_id'),
            )
            project_info, has_project_access = get_project_info(
                scoped_credentials, json_credentials.get('project_id')
            )
            if not has_project_access:
                project_info = dict(projectId=json_credentials.get('project_id'))
                connection_account.configuration_state['project'] = project_info
            else:
                connection_account.configuration_state['project'] = project_info
            connection_account.configuration_state['client_id'] = json_credentials.get(
                'client_id'
            )
            connection_account.save()


def integrate_users(connection_account: ConnectionAccount):
    json_credentials, scoped_credentials = get_gcp_credentials(connection_account)
    project_id = json_credentials.get('project_id')
    response = get_members_from_project(scoped_credentials, project_id)
    members_user, members_service_account = parse_gcp_project_members_binding_response(
        response.get('bindings'), scoped_credentials
    )
    user_mapper = Mapper(
        map_function=_map_member_response, keys=['Id'], laika_object_spec=USER
    )
    update_laika_objects(
        connection_account=connection_account,
        mapper=user_mapper,
        raw_objects=merged_users_with_roles(members_user),
    )
    return members_service_account


def merged_users_with_roles(
    members: List, is_service_account: bool = False
) -> List[Dict[str, Union[str, list]]]:
    emails = set(member.get('email') for member in members)
    merged_users = []
    for email in emails:
        roles = []
        for member in members:
            if email == member.get('email'):
                roles.append(member.get('role'))

        role_id = roles[0] if is_service_account else roles[0].get('name')
        merged_users.append(
            {'id': f'{role_id}.{email}', 'email': email, 'roles': roles}
        )
    return merged_users


def integrate_service_accounts(
    connection_account: ConnectionAccount, service_account_member_with_role: List
):
    json_credentials, scoped_credentials = get_gcp_credentials(connection_account)
    response = get_service_accounts_from_project(
        scoped_credentials,
        json_credentials.get('project_id'),
    )
    service_accounts = response.get('accounts')
    service_accounts_with_all_roles = add_roles_to_service_accounts(
        service_account_members_with_role=service_account_member_with_role,
        service_accounts=service_accounts,
    )

    service_accounts_mapper = Mapper(
        map_function=_map_service_account_response,
        keys=['Id'],
        laika_object_spec=SERVICE_ACCOUNT,
    )
    update_laika_objects(
        connection_account, service_accounts_mapper, service_accounts_with_all_roles
    )


def add_roles_to_service_accounts(
    service_account_members_with_role: List, service_accounts: List
) -> List:
    service_accounts_with_all_roles = []
    service_accounts_with_role = merged_users_with_roles(
        members=service_account_members_with_role, is_service_account=True
    )
    for service_account_role, service_account in itertools.product(
        service_accounts_with_role, service_accounts
    ):
        service_email = service_account.get('email')
        if service_account_role.get('email') == service_email:
            service_account.update({'roles': service_account_role.get('roles')})
            service_accounts_with_all_roles.append(service_account)
        else:
            service_accounts_with_all_roles.append(service_account)
    return service_accounts_with_all_roles


def get_gcp_credentials(connection_account: ConnectionAccount):
    json_credentials = validate_credentials_file(connection_account)
    credentials = get_credentials(json_credentials)
    scoped_credentials = get_credentials_with_scopes(credentials)
    return json_credentials, scoped_credentials


def raise_if_duplicate(connection_account):
    project_id = connection_account.configuration_state.get('project').get('projectId')
    exists = (
        ConnectionAccount.objects.actives(
            configuration_state__project__projectId=project_id,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def validate_credentials_file(connection_account):
    configuration_state = connection_account.configuration_state
    credentials = configuration_state.get('credentials', {})
    credentials_file = credentials.get('credentialsFile', [])
    try:
        if len(credentials_file) > 0:
            credentials_file_body = get_decrypted_or_encrypt_gcp_file(
                connection_account
            )
            credentials = convert_base64_to_json(credentials_file_body)
            for field in REQUIRED_CREDENTIALS_FIELDS:
                if field in credentials:
                    return credentials
                else:
                    raise ConfigurationError.bad_client_credentials()

    except ConfigurationError:
        raise ConfigurationError.bad_client_credentials()


def get_services(connection_account: ConnectionAccount):
    try:
        configuration_state = connection_account.configuration_state
        json_credentials = get_json_credentials(connection_account)
        credentials = get_credentials(json_credentials)
        scope_credentials = get_credentials_with_scopes(credentials)
        project_id = configuration_state.get('project', {}).get('projectId')
        services = get_batch_services_info(scope_credentials, project_id)
        return GoogleCloudServicesType(services=services)
    except ConfigurationError as ce:
        logger.warning(
            f'Connection account {connection_account.id} had an '
            f'error getting services. Error: {ce.error_response}'
        )
        connection_account.result.update(dict(error_response=str(ce.error_response)))
    except Exception as e:
        connection_account.result.update(dict(error_response=str(e)))
    connection_account.save()
    return GoogleCloudServicesType(services=[])


def parse_gcp_project_members_binding_response(
    binding_members_by_role: List, scoped_credentials: Any
) -> Tuple[List, List]:
    members_by_role_user = []
    members_by_role_service_account = []

    for members, role in get_members_by_binding(
        binding_members_by_role, scoped_credentials
    ):
        for member in members:
            split_member_values = member.split(':')
            if len(split_member_values) <= 1:
                continue
            action, member_type, email = _get_split_member_values(split_member_values)
            if action:
                continue
            if member_type == 'user':
                members_by_role_user.append(build_member_info(role, email))
            if member_type == 'serviceAccount':
                members_by_role_service_account.append(
                    build_member_info(role=role, email=email, is_service_account=True)
                )
    return members_by_role_user, members_by_role_service_account


def get_members_by_binding(binding_members_by_role: List, scoped_credentials):
    for binding_member_by_role in binding_members_by_role:
        role_id = binding_member_by_role.get('role')
        role = build_role_with_permissions(role_id, scoped_credentials)
        members = binding_member_by_role.get('members', [])
        yield members, role


def build_member_info(role: Dict, email: str, is_service_account: bool = False) -> Dict:
    return {
        'id': f'{role.get("name")}.{email}',
        'role': role.get('name') if is_service_account else role,
        'email': email,
    }


def build_role_with_permissions(
    role_id: str, scoped_credentials: Any
) -> Dict[str, Union[str, List, object]]:
    permissions = []
    is_custom = is_custom_role(role_id)
    if is_custom:
        permissions = get_role_permissions(
            scoped_credentials=scoped_credentials, role_id=role_id
        )
    role_name = role_id.split('/')[-1]
    role = dict(name=role_name, permissions=permissions, is_custom=is_custom)
    return role


def is_custom_role(role: str) -> bool:
    root = role.split('/')[0]
    return False if 'roles' in root else True
