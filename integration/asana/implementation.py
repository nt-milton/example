import logging
from typing import List

from integration.integration_utils.token_utils import (
    build_fetch_token,
    get_access_token,
)
from integration.utils import calculate_date_range
from objects.system_types import (
    ACCOUNT,
    CHANGE_REQUEST,
    USER,
    resolve_laika_object_type,
)

from ..account import get_integration_laika_objects, integrate_account
from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..models import ConnectionAccount
from ..store import Mapper, update_laika_objects
from ..types import FieldOptionsResponseType
from .mapper import (
    asana_map_project_custom_options,
    map_change_request_response_to_laika_object,
    map_user_response_to_laika_object,
)
from .rest_client import (
    create_access_token,
    create_refresh_token,
    get_projects,
    get_users,
    validate_status_project,
)
from .utils import (
    get_projects_with_workspace,
    get_selected_projects,
    get_selected_workspaces,
    get_tickets_projects,
)

ASANA_SYSTEM = 'Asana'
N_RECORDS = get_integration_laika_objects(ASANA_SYSTEM)

logger = logging.getLogger(__name__)


def clean_up_projects(connection_account: ConnectionAccount) -> None:
    projects = connection_account.settings['projects']
    access_token = get_access_token(connection_account)
    selected_projects = get_selected_projects(
        projects, access_token, connection_account
    )
    available_projects = get_projects(access_token)
    available_projects = [data.get('gid') for data in available_projects]
    updated_projects = list(set(selected_projects) & set(available_projects))
    connection_account.settings['projects'] = updated_projects
    connection_account.save()


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    response = create_refresh_token(code, redirect_uri)
    organization = connection_account.organization
    resolve_laika_object_type(organization, USER)
    resolve_laika_object_type(organization, ACCOUNT)
    resolve_laika_object_type(organization, CHANGE_REQUEST)
    connection_account.authentication = response
    refresh_token = connection_account.authentication['refresh_token']
    access_token = create_access_token(refresh_token)
    projects = get_projects_with_workspace(access_token)
    asana_project_prefetch(connection_account, projects)
    connection_account.save()
    return connection_account


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        clean_up_projects(connection_account)
        raise_if_duplicate(connection_account)
        raise_if_non_access_projects(connection_account)
        integrate_users(connection_account)
        integrate_change_request(connection_account)
        integrate_account(connection_account, ASANA_SYSTEM, N_RECORDS)


def raise_if_duplicate(connection_account: ConnectionAccount):
    data = connection_account.authentication['data']
    exists = (
        ConnectionAccount.objects.actives(
            authentication__data=data, organization=connection_account.organization
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def raise_if_non_access_projects(connection_account: ConnectionAccount) -> None:
    auth_token = get_access_token(connection_account)
    projects = connection_account.settings['projects']
    selected_projects = get_selected_projects(projects, auth_token, connection_account)
    for selected_project in selected_projects:
        validate_status_project(auth_token, selected_project)


def integrate_change_request(connection_account: ConnectionAccount):
    token_provider = build_fetch_token(connection_account)
    projects = connection_account.settings['projects']
    selected_projects = get_selected_projects(
        projects, get_access_token(connection_account), connection_account
    )
    selected_time_range = calculate_date_range()
    tickets = get_tickets_projects(
        token_provider, selected_projects, selected_time_range
    )
    tickets_mapper = Mapper(
        map_function=map_change_request_response_to_laika_object,
        keys=['Key'],
        laika_object_spec=CHANGE_REQUEST,
    )
    update_laika_objects(connection_account, tickets_mapper, tickets)


def integrate_users(connection_account: ConnectionAccount):
    access_token = get_access_token(connection_account)
    projects = connection_account.settings['projects']
    workspaces = get_selected_workspaces(access_token, projects, connection_account)
    users = get_all_users(access_token, workspaces)
    user_mapper = Mapper(
        map_function=map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    update_laika_objects(connection_account, user_mapper, users)


def get_custom_field_options(field_name, connection_account):
    if field_name == 'project':
        return get_projects_options(get_access_token(connection_account))
    else:
        raise NotImplementedError('Not implemented')


def get_projects_options(
    access_token: str,
) -> FieldOptionsResponseType:
    projects = get_projects_with_workspace(access_token)
    return FieldOptionsResponseType(options=asana_map_project_custom_options(projects))


def asana_project_prefetch(connection_account, projects):
    if len(projects) > 0:
        options = asana_map_project_custom_options(projects)
        connection_account.set_prefetched_options('project', options)


def get_all_users(access_token: str, workspaces: List):
    seen_users = set()
    unique_users = []
    for workspace in workspaces:
        workspace_users = get_users(access_token, workspace)
        new_users = []
        for user in workspace_users:
            user_id = user.get('gid')
            if user_id not in seen_users:
                new_users.append(user)
                seen_users.add(user_id)
        unique_users.extend(new_users)
    return unique_users
