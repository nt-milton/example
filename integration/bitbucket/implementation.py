import logging

from integration.account import get_integration_laika_objects, integrate_account
from integration.store import Mapper, update_laika_objects
from integration.utils import calculate_date_range
from objects.system_types import (
    PULL_REQUEST,
    REPOSITORY,
    USER,
    PullRequest,
    Repository,
    User,
)

from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..log_utils import connection_data
from ..models import ConnectionAccount
from ..types import FieldOptionsResponseType
from .rest_client import (
    _get_workspaces,
    get_access_token,
    get_all_workspaces,
    get_pull_requests,
    get_refresh_token,
    get_repositories,
    get_users,
)

logger = logging.getLogger(__name__)

BITBUCKET_SYSTEM = 'Bitbucket'
N_RECORDS = get_integration_laika_objects(BITBUCKET_SYSTEM)


def perform_refresh_token(connection_account: ConnectionAccount) -> None:
    data = connection_data(connection_account)
    refresh_token = connection_account.authentication['refresh_token']
    access_token = get_refresh_token(refresh_token, **data)['access_token']
    if not access_token:
        logger.warning(
            f'Error refreshing token for {BITBUCKET_SYSTEM} '
            f'connection account {connection_account.id}'
        )


def map_user_response_to_laika_object(response, connection_name):
    lo_user = User()
    user = response['user']
    lo_user.id = user['uuid']
    lo_user.first_name = user['display_name']
    lo_user.is_admin = user.get('is_staff', False)
    lo_user.organization_name = ','.join(
        sorted([workspace['name'] for workspace in response['workspaces']])
    )
    lo_user.last_name = ''
    lo_user.title = ''
    lo_user.email = ''
    lo_user.roles = ''
    lo_user.groups = ''
    lo_user.mfa_enabled = user.get('has_2fa_enabled', False)
    lo_user.mfa_enforced = ''
    lo_user.source_system = BITBUCKET_SYSTEM
    lo_user.connection_name = connection_name
    return lo_user.data()


def map_pull_request_to_laika_object(response, connection_name):
    lo_pull_request = PullRequest()
    repository = response['repository']
    pull_request = response['pull_request']
    lo_pull_request.repository = repository['full_name']
    lo_pull_request.repository_visibility = response['pr_visibility']
    lo_pull_request.key = f"{lo_pull_request.repository}-{pull_request['id']}"
    lo_pull_request.target = pull_request['destination']['branch']['name']
    lo_pull_request.source = pull_request['source']['branch']['name']
    lo_pull_request.state = pull_request['state']
    lo_pull_request.title = pull_request['title']
    lo_pull_request.reporter = pull_request['author']['nickname']
    lo_pull_request.created_on = pull_request['created_on']
    lo_pull_request.updated_on = pull_request['updated_on']
    approvals = set(response['approvals'])
    lo_pull_request.is_approved = len(approvals) > 0
    lo_pull_request.is_verified = lo_pull_request.is_approved
    lo_pull_request.approvers = ','.join(sorted(approvals))
    lo_pull_request.organization = repository['workspace']['name']
    pr_id = pull_request['id']
    lo_pull_request.url = (
        f'https://bitbucket.org/{lo_pull_request.repository}/pull-requests/{pr_id}'
    )
    lo_pull_request.source_system = BITBUCKET_SYSTEM
    lo_pull_request.connection_name = connection_name
    return lo_pull_request.data()


def map_repository_to_laika_object(response, connection_name):
    lo_repository = Repository()
    lo_repository.name = response['name']
    lo_repository.organization = response['workspace']['slug']
    lo_repository.public_url = response['links']['html']['href']
    lo_repository.is_active = True
    lo_repository.is_public = not response['is_private']
    lo_repository.updated_at = response['updated_on']
    lo_repository.created_at = response['created_on']
    lo_repository.source_system = BITBUCKET_SYSTEM
    lo_repository.connection_name = connection_name
    return lo_repository.data()


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    data = connection_data(connection_account)
    response = get_access_token(code, **data)
    connection_account.authentication = response
    connection_account.save()
    return connection_account


def run(connection_account):
    with connection_account.connection_attempt():
        data = connection_data(connection_account)
        raise_if_duplicate(connection_account)
        refresh_token = connection_account.authentication['refresh_token']
        access_token = get_refresh_token(refresh_token, **data)['access_token']
        get_selected_workspaces(connection_account, access_token)
        integrate_users(connection_account, access_token)
        integrate_pull_requests(connection_account, access_token)
        integrate_repositories(connection_account, access_token)
        integrate_account(connection_account, BITBUCKET_SYSTEM, N_RECORDS)


def get_users_merged_by_workspaces(records):
    merged_users = {}
    for record in records:
        user, workspace = record['user'], record['workspace']
        if user['uuid'] not in merged_users:
            merged_users[user['uuid']] = {'user': user, 'workspaces': []}
        merged_users[user['uuid']]['workspaces'].append(workspace)
    return list(merged_users.values())


def get_selected_workspaces(connection_account, access_token):
    selected_workspaces = connection_account.settings.get('workspaces', [])
    if 'All Workspaces Selected' in selected_workspaces:
        workspaces = _get_workspaces(access_token)
        connection_account.settings['workspaces'] = [
            workspace.get('slug') for workspace in workspaces
        ]
        connection_account.save()
        return connection_account.settings.get('workspaces', [])


def integrate_users(connection_account: ConnectionAccount, access_token: str):
    data = connection_data(connection_account)
    user_mapper = Mapper(
        map_function=map_user_response_to_laika_object,
        keys=['Id', 'Organization Name'],
        laika_object_spec=USER,
    )
    selected_workspaces = connection_account.settings.get('workspaces')
    records = get_users(access_token, selected_workspaces, **data)
    merged_users = get_users_merged_by_workspaces(records)
    update_laika_objects(connection_account, user_mapper, merged_users)


def integrate_pull_requests(connection_account: ConnectionAccount, access_token: str):
    data = connection_data(connection_account)
    selected_workspaces = connection_account.settings.get('workspaces')
    selected_repo_visibility = connection_account.settings.get('visibility')
    selected_time_range = calculate_date_range()
    pr_mapper = Mapper(
        map_function=map_pull_request_to_laika_object,
        keys=['Key', 'Organization'],
        laika_object_spec=PULL_REQUEST,
    )
    records = get_pull_requests(
        access_token,
        selected_workspaces,
        selected_repo_visibility,
        selected_time_range,
        **data,
    )
    update_laika_objects(connection_account, pr_mapper, records)


def integrate_repositories(connection_account: ConnectionAccount, access_token: str):
    data = connection_data(connection_account)
    selected_workspaces = connection_account.settings.get('workspaces')
    selected_repo_visibility = connection_account.settings.get('visibility')

    repository_mapper = Mapper(
        map_function=map_repository_to_laika_object,
        keys=['Organization', 'Name'],
        laika_object_spec=REPOSITORY,
    )
    records = get_repositories(
        access_token, selected_workspaces, selected_repo_visibility, **data
    )
    update_laika_objects(connection_account, repository_mapper, records)


def raise_if_duplicate(connection_account):
    refresh_token = connection_account.authentication['refresh_token']
    exists = (
        ConnectionAccount.objects.actives(
            authentication__refresh_token=refresh_token,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def get_custom_field_options(field_name: str, connection_account: ConnectionAccount):
    data = connection_data(connection_account)
    refresh_token = connection_account.authentication['refresh_token']
    access_token = get_refresh_token(refresh_token, **data)['access_token']
    if field_name == 'workspace':
        all_workspaces = get_all_workspaces(access_token, **data)
        return _get_workspaces_options(all_workspaces)
    else:
        raise NotImplementedError('Not implemented')


def _get_workspaces_options(workspaces):
    workspaces_options = []
    for workspace in workspaces:
        workspaces_options.append(
            {
                'id': workspace['slug'],
                'value': {
                    'name': workspace['name'],
                },
            }
        )
    return FieldOptionsResponseType(options=workspaces_options)
