import integration.integration_utils.token_utils as token_utils
from integration.account import get_integration_laika_objects, integrate_account
from integration.azure_devops import rest_client
from integration.azure_devops.constants import AZURE_DEVOPS_SYSTEM
from integration.azure_devops.mapper import (
    map_pull_request_response_to_laika_object,
    map_repository_response_to_laika_object,
    map_users_response_to_laika_object,
)
from integration.azure_devops.rest_client import create_refresh_token
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from integration.types import FieldOptionsResponseType
from integration.utils import prefetch
from objects.system_types import PULL_REQUEST, REPOSITORY, USER

N_RECORDS = get_integration_laika_objects(AZURE_DEVOPS_SYSTEM)


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    response = create_refresh_token(code, redirect_uri)
    connection_account.authentication = response
    if 'refresh_token' in response:
        prefetch(connection_account, 'organization')
    connection_account.save()
    return connection_account


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        organization: str = connection_account.settings.get('organization')
        token = token_utils.get_access_token(connection_account)
        projects = rest_client.get_projects(token, organization)
        integrate_repositories(connection_account, organization, projects)
        integrate_pull_requests(connection_account, organization, projects)
        integrate_users(connection_account, organization)
        integrate_account(connection_account, AZURE_DEVOPS_SYSTEM, N_RECORDS)


def integrate_repositories(
    connection_account: ConnectionAccount, organization: str, projects: list[dict]
):
    token = token_utils.get_access_token(connection_account)
    repositories = _read_repositories(token, organization, projects)
    repository_mapper = Mapper(
        map_function=map_repository_response_to_laika_object,
        keys=['Organization', 'Name'],
        laika_object_spec=REPOSITORY,
    )
    update_laika_objects(connection_account, repository_mapper, repositories)


def integrate_pull_requests(
    connection_account: ConnectionAccount, organization: str, projects: list[dict]
):
    token = token_utils.get_access_token(connection_account)
    pull_requests = _read_pull_request(organization, projects, token)
    repository_mapper = Mapper(
        map_function=map_pull_request_response_to_laika_object,
        keys=['Key', 'Organization'],
        laika_object_spec=PULL_REQUEST,
    )
    update_laika_objects(connection_account, repository_mapper, pull_requests)


def _read_pull_request(organization, projects, token):
    pull_requests = []
    for project in projects:
        pull_requests += rest_client.get_pull_request_by_project(
            token, organization, project.get('id')
        )
    for pr in pull_requests:
        pr['organization'] = organization
        yield pr


def integrate_users(connection_account: ConnectionAccount, organization: str):
    token = token_utils.get_access_token(connection_account)
    users = _read_users(token, organization)
    repository_mapper = Mapper(
        map_function=map_users_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    update_laika_objects(connection_account, repository_mapper, users)


def _read_repositories(token: str, organization: str, projects: list[dict]):
    repositories = []
    for project in projects:
        repositories += rest_client.get_repositories(
            token, organization, project.get('id')
        )
    for repository in repositories:
        repository['organization'] = organization
        yield repository


def _read_users(token: str, organization: str):
    members = rest_client.get_users(token, organization)
    user_ids: list[str] = []
    for member in members:
        user_ids.append(member.get('id'))

    for user_id in user_ids:
        user_with_entitlement = rest_client.get_users_entitlements(
            token, organization, user_id
        )
        user_with_entitlement['organization'] = organization
        yield user_with_entitlement


def get_custom_field_options(
    field_name: str, connection_account: ConnectionAccount
) -> FieldOptionsResponseType:
    if field_name != 'organization':
        raise NotImplementedError('Not implemented')
    token = token_utils.get_access_token(connection_account)
    member = rest_client.get_account_member_id(token)
    member_id = member.get('id')
    organizations = rest_client.get_organizations(
        access_token=token, member_id=member_id
    )
    return _map_options(organizations)


def _map_options(organizations):
    options: list[dict] = []
    for org in organizations:
        options.append(
            {'id': org['accountName'], 'value': {'name': org['accountName']}}
        )
    return FieldOptionsResponseType(options=options)


def raise_if_duplicate(connection_account: ConnectionAccount):
    organization = connection_account.settings['organization']
    exists = (
        ConnectionAccount.objects.actives(
            configuration_state__settings__organization=organization,
            organization=connection_account.organization,
            integration__vendor__name='Azure DevOps',
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()
