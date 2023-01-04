import logging
from collections import namedtuple
from typing import List, Tuple

from integration.account import get_integration_laika_objects, integrate_account
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.github import http_client
from integration.github.mapper import (
    GithubUser,
    TeamMembers,
    map_pull_requests_to_laika_object,
    map_repository_to_laika_object,
    map_users_to_laika_object,
)
from integration.log_utils import connection_data
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from integration.types import FieldOptionsResponseType
from integration.utils import calculate_date_range, prefetch
from objects.system_types import (
    PULL_REQUEST,
    REPOSITORY,
    USER,
    resolve_laika_object_type,
)

logger = logging.getLogger(__name__)

GITHUB_SYSTEM = 'GitHub'
N_RECORDS = get_integration_laika_objects(GITHUB_SYSTEM)


def perform_refresh_token(connection_account: ConnectionAccount) -> None:
    token = connection_account.authentication['access_token']
    if not token:
        logger.warning(
            f'Error getting token for {GITHUB_SYSTEM} '
            f'connection account {connection_account.id}'
        )


def callback(code: str, redirect_uri: str, connection_account: ConnectionAccount):
    if not code:
        raise ConfigurationError.denial_of_consent()

    data = connection_data(connection_account)
    response = http_client.create_refresh_token(code, redirect_uri, **data)
    github_orgs = _get_github_organization_names(response['access_token'], **data)
    connection_account.authentication = response
    connection_account.authentication['github_orgs'] = github_orgs
    _validate_missing_org(connection_account)
    organization = connection_account.organization
    resolve_laika_object_type(organization, PULL_REQUEST)
    if 'access_token' in response:
        prefetch(connection_account, 'organization')
    connection_account.save()
    return connection_account


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        token = connection_account.authentication['access_token']
        integrate_pull_requests(connection_account, token)
        integrate_repositories(connection_account, token)
        if 'user' in connection_account.authentication['scope']:
            integrate_users(connection_account, token)
        integrate_account(connection_account, GITHUB_SYSTEM, N_RECORDS)


def _get_github_organization_names(token: str, **kwargs):
    organizations = http_client.read_all_github_organizations(token, **kwargs)
    return [org['login_name'] for org in organizations]


def _get_github_organizations(token: str, **kwargs):
    organizations = http_client.read_all_github_organizations(token, **kwargs)
    return [
        {'id': str(org['login_name']), 'name': org['profile_name']}
        for org in organizations
    ]


def _get_configuration_settings(connection_account: ConnectionAccount):
    selected_organizations = None
    selected_repo_visibility = None

    if not connection_account.settings:
        return selected_organizations, selected_repo_visibility

    selected_organizations = connection_account.settings.get('organizations', None)
    selected_repo_visibility = connection_account.settings.get('visibility', None)
    return selected_organizations, selected_repo_visibility


def integrate_pull_requests(connection_account: ConnectionAccount, token: str):
    data = connection_data(connection_account)
    selected_organizations, selected_repo_visibility = _get_configuration_settings(
        connection_account
    )
    github_organizations = (
        selected_organizations
        if selected_organizations
        else _get_github_organization_names(token, **data)
    )
    selected_time_range = calculate_date_range()
    connection_account.authentication['github_orgs'] = github_organizations
    _validate_connection(connection_account)
    records = _read_all_pull_requests(
        token,
        github_organizations,
        selected_repo_visibility,
        selected_time_range,
        **data,
    )
    pr_mapper = Mapper(
        map_function=map_pull_requests_to_laika_object,
        keys=['Key', 'Organization'],
        laika_object_spec=PULL_REQUEST,
    )
    update_laika_objects(connection_account, pr_mapper, records)


def integrate_users(connection_account: ConnectionAccount, token: str):
    github_organizations = connection_account.authentication['github_orgs']
    data = connection_data(connection_account)
    user_records = _read_all_organization_users(github_organizations, token, **data)
    user_mapper = Mapper(
        map_function=map_users_to_laika_object,
        keys=['Id', 'Organization Name'],
        laika_object_spec=USER,
    )
    update_laika_objects(connection_account, user_mapper, user_records)


PullRequestRecord = namedtuple(
    'PullRequestRecord', ('organization', 'repository', 'pr', 'pr_visibility')
)


def _read_all_pull_requests(
    token: str,
    github_orgs: list,
    repo_visibility: str,
    selected_time_range: str,
    **kwargs,
):
    for github_org in github_orgs:
        pull_requests = http_client.read_all_pull_requests(
            github_org, repo_visibility, token, selected_time_range, **kwargs
        )
        for repo_name, pr, pr_visibility in pull_requests:
            yield PullRequestRecord(github_org, repo_name, pr, pr_visibility)


def integrate_repositories(connection_account: ConnectionAccount, token: str):
    data = connection_data(connection_account)
    github_organizations = connection_account.authentication['github_orgs']
    repo_visibility = connection_account.settings.get('visibility')
    _validate_connection(connection_account)

    repository_records = _read_all_repositories(
        github_organizations, repo_visibility, token, **data
    )
    repository_mapper = Mapper(
        map_function=map_repository_to_laika_object,
        keys=['Organization', 'Name'],
        laika_object_spec=REPOSITORY,
    )
    update_laika_objects(connection_account, repository_mapper, repository_records)


RepositoryRecord = namedtuple('RepositoryRecord', ('organization', 'repository'))


def _read_all_repositories(
    github_orgs: list, selected_repo_visibility: str, token: str, **kwargs
):
    for github_org in github_orgs:
        repositories = http_client.read_all_repositories(
            github_org, selected_repo_visibility, token, **kwargs
        )
        for repository in repositories:
            yield RepositoryRecord(github_org, repository)


def _read_all_organization_users(
    github_organizations: List, access_token: str, **kwargs
):
    for github_organization in github_organizations:
        organization_users = http_client.read_all_organization_users(
            github_organization=github_organization, access_token=access_token, **kwargs
        )
        members_by_teams = http_client.read_all_organization_members_by_teams(
            github_organization=github_organization, access_token=access_token, **kwargs
        )
        team_members: List[Tuple] = []
        for members_by_team in members_by_teams:
            team_members.append(
                TeamMembers(
                    team=members_by_team.get('name'),
                    members=[
                        user.get('login')
                        for user in members_by_team.get('members', {}).get('nodes', [])
                    ],
                )
            )

        for user in organization_users:
            user_data = user['node']
            yield GithubUser(
                id=user_data.get('id'),
                name=user_data.get('name'),
                role=user.get('role'),
                email=user_data.get('email'),
                title=user_data.get('login'),
                has_2fa=user.get('hasTwoFactorEnabled', False),
                organization_name=user_data.get('organization', {}).get('name'),
                teams=[
                    team[0]
                    for team in list(
                        filter(
                            lambda members: user_data.get('login') in members[1],
                            team_members,
                        )
                    )
                ],
            )


def _validate_connection(connection_account: ConnectionAccount):
    _validate_missing_org(connection_account)
    _validate_duplicate(connection_account)


def _validate_duplicate(connection_account: ConnectionAccount):
    github_orgs = connection_account.authentication['github_orgs']
    exists = (
        ConnectionAccount.objects.actives(
            authentication__github_orgs=github_orgs,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def _validate_missing_org(connection_account: ConnectionAccount):
    github_orgs = connection_account.authentication['github_orgs']
    if not github_orgs:
        raise ConfigurationError.missing_github_organization()


def get_custom_field_options(field_name: str, connection_account: ConnectionAccount):
    if field_name == 'organization':
        data = connection_data(connection_account)
        token = connection_account.authentication['access_token']
        organizations = _get_github_organizations(token, **data)
        return _get_organization_options(organizations)
    else:
        raise NotImplementedError('Not implemented')


def _get_organization_options(organizations: list):
    organization_options = []
    for organization in organizations:
        organization_options.append(
            {'id': organization['id'], 'value': {'name': organization['name']}}
        )
    return FieldOptionsResponseType(options=organization_options)
