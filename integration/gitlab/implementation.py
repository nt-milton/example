import logging
from collections import namedtuple
from typing import Dict, Generator, List, Optional, Tuple

from integration.account import get_integration_laika_objects, integrate_account
from integration.constants import SELF_MANAGED_SUBSCRIPTION
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.gitlab.http_client import (
    AccessTokenRequest,
    create_access_token,
    create_refresh_token,
    read_all_gitlab_groups,
    read_merge_request_gitlab,
    read_projects_gitlab,
    read_users_group,
)
from integration.log_utils import connection_data
from integration.models import ConnectionAccount
from integration.settings import GITLAB_BASE_URL, GITLAB_CLIENT_ID, GITLAB_CLIENT_SECRET
from integration.store import Mapper, update_laika_objects
from integration.types import FieldOptionsResponseType
from integration.utils import calculate_date_range, prefetch
from objects.system_types import (
    ACCOUNT,
    PULL_REQUEST,
    REPOSITORY,
    USER,
    PullRequest,
    Repository,
    User,
    resolve_laika_object_type,
)

logger = logging.getLogger(__name__)

GITLAB_SYSTEM = 'GitLab'
N_RECORDS = get_integration_laika_objects(GITLAB_SYSTEM)


def connect(connection_account):
    pass  # this is not required in this integration


def perform_refresh_token(connection_account: ConnectionAccount):
    access_token = connection_account.authentication['access_token']
    if not access_token:
        logger.warning(
            f'Error getting token for {GITLAB_SYSTEM} '
            f'connection account {connection_account.id}'
        )


def _map_pull_request_response_to_laika_object(response, connection_name):
    pull_request = response.pull_request
    approvers = {approver['name'] for approver in pull_request['approvedBy']['nodes']}
    lo_pull_request = PullRequest()
    lo_pull_request.repository = pull_request['project']['name']
    lo_pull_request.repository_visibility = response.project_visibility
    pr_id = pull_request['iid']
    lo_pull_request.key = f'{lo_pull_request.repository}-{pr_id}'
    lo_pull_request.target = pull_request['targetBranch']
    lo_pull_request.source = pull_request['sourceBranch']
    lo_pull_request.state = pull_request['state']
    lo_pull_request.title = pull_request['title']
    lo_pull_request.is_verified = pull_request['approvalsLeft'] == 0
    lo_pull_request.is_approved = pull_request['approved']
    lo_pull_request.url = pull_request['webUrl']
    lo_pull_request.approvers = ','.join(sorted(approvers))
    lo_pull_request.reporter = pull_request['author']['name']
    lo_pull_request.created_on = pull_request['createdAt']
    lo_pull_request.updated_on = pull_request['updatedAt']
    lo_pull_request.organization = response.group
    lo_pull_request.source_system = GITLAB_SYSTEM
    lo_pull_request.connection_name = connection_name
    return lo_pull_request.data()


def build_map_function(connection_account: ConnectionAccount):
    def _map_user_response_to_laika_object(response, connection_name):
        user = response['user']
        organization_id = _get_org_id_by_subscription_type(connection_account)
        formatted_id: str = user['id'].replace('gid://gitlab/User/', '')
        memberships = user['groupMemberships']['nodes']
        roles = {
            role['accessLevel']['stringValue'].capitalize() for role in memberships
        }
        groups = {group['group']['name'] for group in memberships}
        user_id = (
            f'{organization_id}-{formatted_id}' if organization_id else formatted_id
        )
        two_factor_enforce_list: List[bool] = [
            two_factor_enabled['group']['requireTwoFactorAuthentication']
            for two_factor_enabled in memberships
        ]
        lo_user = User()
        lo_user.id = user_id
        lo_user.first_name = user['name']
        lo_user.last_name = ''
        lo_user.email = user['publicEmail']
        lo_user.title = ''
        lo_user.is_admin = user.get('isAdmin', False)
        lo_user.roles = ', '.join(sorted(roles))
        lo_user.groups = ', '.join(sorted(groups))
        lo_user.mfa_enabled = ''
        lo_user.mfa_enforced = sum(two_factor_enforce_list) != 0
        lo_user.organization_name = ''
        lo_user.connection_name = connection_name
        lo_user.source_system = GITLAB_SYSTEM
        return lo_user.data()

    return _map_user_response_to_laika_object


def _map_repository_response_to_laika_object(response, connection_name):
    repository = response[1]
    group = response[0]
    lo_repository = Repository()
    lo_repository.name = repository['name']
    lo_repository.organization = group
    lo_repository.public_url = repository['webUrl']
    lo_repository.is_active = not repository['archived']
    lo_repository.is_public = repository['visibility'] == "public"
    lo_repository.updated_at = repository['lastActivityAt']
    lo_repository.created_at = repository['createdAt']
    lo_repository.connection_name = connection_name
    lo_repository.source_system = GITLAB_SYSTEM
    return lo_repository.data()


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    data = connection_data(connection_account)
    configuration_state = connection_account.configuration_state
    response = create_refresh_token(
        code=code,
        redirect_uri=redirect_uri,
        **_add_credentials(configuration_state, **data),
    )
    organization = connection_account.organization
    resolve_laika_object_type(organization, ACCOUNT)
    resolve_laika_object_type(organization, PULL_REQUEST)
    resolve_laika_object_type(organization, USER)
    resolve_laika_object_type(organization, REPOSITORY)
    connection_account.authentication = response
    if 'access_token' in response:
        prefetch(connection_account, 'group')
    connection_account.save()
    return connection_account


def _get_access_token_request(
    connection_account: ConnectionAccount,
) -> AccessTokenRequest:
    return AccessTokenRequest(
        client_id=connection_account.credentials.get('clientId', GITLAB_CLIENT_ID),
        client_secret=connection_account.credentials.get(
            'secretId', GITLAB_CLIENT_SECRET
        ),
        oauth_url=connection_account.credentials.get('baseUrl', GITLAB_BASE_URL)
        + '/oauth/token',
        redirect_uri=connection_account.integration.metadata['param_redirect_uri'],
    )


def _perform_create_access_token(connection_account: ConnectionAccount):
    data = connection_data(connection_account)
    access_token_request = _get_access_token_request(connection_account)
    prev_refresh_token = create_access_token(
        connection_account.authentication['refresh_token'], access_token_request, **data
    )
    access_token, refresh_token = prev_refresh_token
    connection_account.authentication['refresh_token'] = refresh_token
    connection_account.authentication['access_token'] = access_token
    connection_account.save()
    return access_token


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        access_token = _perform_create_access_token(connection_account)
        integrate_pull_requests(connection_account, access_token)
        integrate_users(connection_account, access_token)
        integrate_repositories(connection_account, access_token)
        integrate_account(connection_account, GITLAB_SYSTEM, N_RECORDS)


def integrate_users(connection_account: ConnectionAccount, access_token: str):
    data = connection_data(connection_account)
    credentials = connection_account.configuration_state

    selected_groups, _ = _get_configuration_settings(connection_account)

    _map_user_response_to_laika_object = build_map_function(connection_account)
    user_mapper = Mapper(
        map_function=_map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    users = _read_gitlab_group_users(
        groups=_get_groups(selected_groups),
        access_token=access_token,
        **_add_credentials(credentials=credentials, **data),
    )
    update_laika_objects(connection_account, user_mapper, users)


def _read_gitlab_group_users(
    groups: List[str], access_token: str, **kwargs
) -> Generator[Dict, str, None]:
    for group in groups:
        users = read_users_group(access_token=access_token, group_name=group, **kwargs)
        for user in users:
            yield user


def integrate_pull_requests(
    connection_account: ConnectionAccount, access_token: str
) -> None:
    selected_groups, selected_visibility = _get_configuration_settings(
        connection_account
    )
    selected_time_range = calculate_date_range()
    data = connection_data(connection_account)
    credentials = connection_account.configuration_state
    pull_request_mapper = Mapper(
        map_function=_map_pull_request_response_to_laika_object,
        keys=['Key', 'Organization'],
        laika_object_spec=PULL_REQUEST,
    )
    pull_requests = _read_gitlab_pull_request(
        groups=_get_groups(selected_groups),
        visibility=selected_visibility,
        access_token=access_token,
        selected_time_range=selected_time_range,
        **_add_credentials(credentials=credentials, **data),
    )
    update_laika_objects(connection_account, pull_request_mapper, pull_requests)


GitlabPullRequest = namedtuple(
    'GitlabPullRequest', ('group', 'pull_request', 'project_visibility')
)


def _read_gitlab_pull_request(
    groups: List[str],
    visibility: str,
    access_token: str,
    selected_time_range: str,
    **kwargs,
) -> Generator[GitlabPullRequest, str, None]:
    for group in groups:
        pull_requests = read_merge_request_gitlab(
            access_token=access_token,
            group_name=group,
            selected_time_range=selected_time_range,
            visibility=visibility,
            **kwargs,
        )
        for group_name, pull_request, project_visibility in pull_requests:
            yield GitlabPullRequest(group_name, pull_request, project_visibility)


def integrate_repositories(
    connection_account: ConnectionAccount, access_token: str
) -> None:
    selected_groups, selected_visibility = _get_configuration_settings(
        connection_account
    )

    data = connection_data(connection_account)
    credentials = connection_account.configuration_state

    repository_mapper = Mapper(
        map_function=_map_repository_response_to_laika_object,
        keys=['Organization', 'Name'],
        laika_object_spec=REPOSITORY,
    )
    repositories = _read_gitlab_repositories(
        groups=_get_groups(selected_groups),
        access_token=access_token,
        visibility=selected_visibility,
        **_add_credentials(credentials=credentials, **data),
    )
    update_laika_objects(connection_account, repository_mapper, repositories)


RepositoryRecord = namedtuple('RepositoryRecord', ('group', 'repositories'))


def _read_gitlab_repositories(
    groups: List[str], access_token: str, visibility: str, **kwargs
) -> Generator[RepositoryRecord, str, None]:
    for group in groups:
        projects = read_projects_gitlab(
            access_token=access_token, group_name=group, visibility=visibility, **kwargs
        )
        for group_name, project in projects:
            yield RepositoryRecord(group_name, project)


def get_custom_field_options(
    field_name: str, connection_account: ConnectionAccount
) -> FieldOptionsResponseType:
    token = connection_account.authentication['access_token']
    if field_name == 'group':
        data = connection_data(connection_account)
        credentials = connection_account.configuration_state
        groups = read_all_gitlab_groups(
            token, **_add_credentials(credentials=credentials, **data)
        )
        return _get_group_options(groups)
    else:
        raise NotImplementedError('Not implemented')


def _get_group_options(groups: List[Dict]) -> FieldOptionsResponseType:
    group_options = []
    for group in groups:
        group_options.append(
            {'id': group['fullPath'], 'value': {'name': group['fullName']}}
        )
    return FieldOptionsResponseType(options=group_options)


def _get_configuration_settings(
    connection_account: ConnectionAccount,
) -> Tuple[List[str], str]:
    selected_groups = _get_groups_by_condition(connection_account)
    selected_visibility = connection_account.settings.get('visibility', None)
    return selected_groups, selected_visibility


def raise_if_duplicate(connection_account: ConnectionAccount):
    groups = connection_account.settings.get('groups', [])
    if groups is not None:
        exists = (
            ConnectionAccount.objects.actives(
                configuration_state__settings__groups__contains=groups,
                organization=connection_account.organization,
            )
            .exclude(id=connection_account.id)
            .exists()
        )
        if exists:
            raise ConnectionAlreadyExists()


def _get_groups(groups: List[str]) -> List[str]:
    return groups if groups else []


def _add_credentials(credentials: Dict, **kwargs) -> Dict:
    return {**dict(credentials=credentials), **kwargs}


def _get_groups_by_condition(connection_account: ConnectionAccount) -> List[str]:
    token = connection_account.authentication['access_token']
    data = connection_data(connection_account)
    credentials = connection_account.configuration_state
    selected_groups = connection_account.settings.get('groups', [])
    if 'all' in selected_groups:
        groups = read_all_gitlab_groups(
            token, **_add_credentials(credentials=credentials, **data)
        )
        return [group['fullPath'] for group in groups]
    return selected_groups


def _get_org_id_by_subscription_type(connection: ConnectionAccount) -> Optional[str]:
    subscription_type: str = connection.configuration_state.get('subscriptionType', '')
    if subscription_type == SELF_MANAGED_SUBSCRIPTION:
        return connection.organization.id

    return None
