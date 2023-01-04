import logging
from typing import Any

import integration.integration_utils.token_utils as token_utils
from integration.account import get_integration_laika_objects, integrate_account
from integration.azure_boards import rest_client
from integration.azure_boards.constants import (
    AZURE_BOARDS_SYSTEM,
    WORK_ITEMS_PER_REQUEST,
    WORK_ITEMS_QUERY,
)
from integration.azure_boards.mapper import map_work_item_to_laika_object
from integration.azure_devops import rest_client as rest_client_devops
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from integration.types import FieldOptionsResponseType
from integration.utils import prefetch
from laika.utils.list import split_list_in_chunks
from objects.system_types import CHANGE_REQUEST

logger = logging.getLogger(__name__)

N_RECORDS = get_integration_laika_objects(AZURE_BOARDS_SYSTEM)


def callback(code, redirect_uri, connection_account) -> ConnectionAccount:
    if not code:
        raise ConfigurationError.denial_of_consent()

    response = rest_client.create_refresh_token(code, redirect_uri)
    connection_account.authentication = response
    if 'refresh_token' in response:
        prefetch(connection_account, 'organizations')
        prefetch(connection_account, 'projects')
    connection_account.save()
    return connection_account


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        integrate_change_requests(connection_account)
        integrate_account(connection_account, AZURE_BOARDS_SYSTEM, N_RECORDS)


def _get_work_items_query(access_token: str, organization: str, project: str) -> Any:
    query = rest_client.get_query_by_id(
        access_token,
        organization,
        project,
        'My Queries/Azure Boards Laika Integration',
    )
    if not query.ok:
        query = rest_client.create_work_item_query(
            access_token,
            organization,
            project,
            'My Queries',
            'Azure Boards Laika Integration',
            WORK_ITEMS_QUERY.format(project=project),
        )
    return query


def _get_work_item_ids(access_token: str, organization: str, project: str) -> list[str]:
    query = _get_work_items_query(access_token, organization, project)
    wiql = rest_client.get_wiql_from_query(access_token, query)
    return [str(work_item['id']) for work_item in wiql.json()['workItems']]


def _get_work_item_with_updates_from_values(
    access_token: str, work_item_values: Any, read_history: bool
) -> list[dict]:
    work_items_with_updates = []
    for work_item in work_item_values:
        work_item_updates = (
            rest_client.get_work_item_updates(access_token, work_item).json()
            if read_history
            else {}
        )
        work_items_with_updates.append(
            {'work_item': work_item, 'work_item_updates': work_item_updates}
        )
    return work_items_with_updates


def _read_work_items(
    access_token: str, organization: str, projects: list[str], read_history: bool
) -> list[dict]:
    work_items = []
    for project in projects:
        work_item_ids = _get_work_item_ids(access_token, organization, project)
        sliced_work_item_ids = split_list_in_chunks(
            work_item_ids, WORK_ITEMS_PER_REQUEST
        )
        for ids in sliced_work_item_ids:
            work_item_values = rest_client.get_work_items_by_ids(
                access_token, organization, project, ids
            ).json()['value']
            work_items_with_updates = _get_work_item_with_updates_from_values(
                access_token, work_item_values, read_history
            )
            work_items.extend(work_items_with_updates)
    return work_items


def _read_all_projects(access_token: str, organization: str) -> list[str]:
    return [
        project['name']
        for project in rest_client_devops.get_projects(access_token, organization)
    ]


def _get_work_items(connection_account: ConnectionAccount) -> list[dict]:
    token = token_utils.get_access_token(connection_account)
    organization = connection_account.settings.get('organization')
    select_all_projects = connection_account.settings.get('select_all_projects')
    projects = (
        _read_all_projects(token, organization)
        if select_all_projects
        else connection_account.settings.get('projects')
    )
    integration_metadata = connection_account.integration.metadata
    read_history = integration_metadata.get('read_history')
    return _read_work_items(token, organization, projects, read_history)


def integrate_change_requests(connection_account: ConnectionAccount):
    work_items = _get_work_items(connection_account)
    change_request_mapper = Mapper(
        map_function=map_work_item_to_laika_object,
        keys=['Url'],
        laika_object_spec=CHANGE_REQUEST,
    )
    update_laika_objects(connection_account, change_request_mapper, work_items)


def _get_organization_options(
    access_token: str, connection_account: ConnectionAccount
) -> FieldOptionsResponseType:
    member = rest_client_devops.get_account_member_id(access_token)
    member_id = member.get('id')
    original_organizations = rest_client_devops.get_organizations(
        access_token=access_token, member_id=member_id
    )
    final_organizations = []
    for organization in original_organizations:
        organization_name = organization['accountName']
        projects_response = rest_client_devops.get_projects_raw_response(
            access_token, organization_name
        )
        if projects_response.ok:
            final_organizations.append(organization)
        else:
            logger.info(
                f'Organization {organization_name} is omitted because internal '
                'resources are not exposed. '
                f'Connection account {connection_account.id}'
            )
    return _map_organization_options(final_organizations)


def _get_project_options(
    access_token: str, connection_account: ConnectionAccount
) -> FieldOptionsResponseType:
    organizations = connection_account.authentication.get('prefetch_organizations')
    projects_per_organizations = []
    for organization in organizations:
        organization_id = organization['id']
        projects_response = rest_client_devops.get_projects(
            access_token, organization_id
        )
        projects_per_organizations.append(
            {'id': organization_id, 'value': _map_project_options(projects_response)}
        )
    return FieldOptionsResponseType(options=projects_per_organizations)


def get_custom_field_options(
    field_name: str, connection_account: ConnectionAccount
) -> FieldOptionsResponseType:
    token = token_utils.get_access_token(connection_account)
    if field_name == 'organizations':
        return _get_organization_options(token, connection_account)
    elif field_name == 'projects':
        return _get_project_options(token, connection_account)
    else:
        raise NotImplementedError('Not implemented')


def _map_organization_options(organizations: list[dict]) -> FieldOptionsResponseType:
    options: list[dict] = [
        {
            'id': organization['accountName'],
            'value': {'name': organization['accountName']},
        }
        for organization in organizations
    ]
    return FieldOptionsResponseType(options=options)


def _map_project_options(projects) -> list[dict]:
    return [
        {'id': project['id'], 'value': {'name': project['name']}}
        for project in projects
    ]


def raise_if_duplicate(connection_account: ConnectionAccount):
    organization = connection_account.settings['organization']
    projects = connection_account.settings['projects']
    exists = (
        ConnectionAccount.objects.actives(
            configuration_state__settings__organization=organization,
            configuration_state__settings__projects=projects,
            organization=connection_account.organization,
            integration__vendor__name='Azure Boards',
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()
