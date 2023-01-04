import logging

from integration.account import get_integration_laika_objects, integrate_account
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.linear.constants import INSUFFICIENT_PERMISSIONS
from integration.linear.mapper import (
    LINEAR_SYSTEM,
    map_change_request_response_to_laika_object,
    map_users_response_to_laika_object,
)
from integration.linear.rest_client import (
    get_access_token,
    get_current_user,
    get_issues,
    get_projects,
    get_users,
)
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from integration.types import FieldOptionsResponseType
from integration.utils import resolve_laika_object_types
from objects.system_types import ACCOUNT, CHANGE_REQUEST, USER

logger = logging.getLogger(__name__)

CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE = 'linearTransitionsHistory'
N_RECORDS = get_integration_laika_objects(LINEAR_SYSTEM)


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    response = get_access_token(code, redirect_uri)
    organization = connection_account.organization
    resolve_laika_object_types(organization, [ACCOUNT, USER, CHANGE_REQUEST])
    connection_account.authentication = response
    with connection_account.connection_error(
        error_code=INSUFFICIENT_PERMISSIONS, keep_exception_error=True
    ):
        user_data = get_current_user(
            connection_account.authentication['access_token'],
        )
        connection_account.authentication['data'] = user_data
        if not user_data.get('admin'):
            error_response = dict(
                user_data=user_data, message='The user does not have admin permissions'
            )
            raise ConfigurationError.insufficient_permission(response=error_response)
    access_token = connection_account.authentication['access_token']
    linear_project_prefetch(connection_account, get_projects(access_token))
    connection_account.save()
    return connection_account


def integrate_change_request(connection_account: ConnectionAccount):
    access_token = connection_account.authentication['access_token']
    selected_projects = get_selected_projects(access_token, connection_account)
    issues = get_issues(access_token, selected_projects)
    issues_mapper = Mapper(
        map_function=map_change_request_response_to_laika_object,
        keys=['Key'],
        laika_object_spec=CHANGE_REQUEST,
    )
    update_laika_objects(connection_account, issues_mapper, issues)


def integrate_users(connection_account: ConnectionAccount):
    access_token = connection_account.authentication['access_token']
    users = get_users(access_token)
    users_mapper = Mapper(
        map_function=map_users_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    update_laika_objects(connection_account, users_mapper, users)


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        integrate_users(connection_account)
        integrate_change_request(connection_account)
        integrate_account(connection_account, LINEAR_SYSTEM, N_RECORDS)


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


def linear_map_project_custom_options(options_generator):
    projects = []
    for project in options_generator:
        projects.append({'id': project['id'], 'value': {'name': project['name']}})
    return projects


def linear_project_prefetch(connection_account: ConnectionAccount, projects: list):
    if len(projects) > 0:
        options = linear_map_project_custom_options(projects)
        connection_account.set_prefetched_options('project', options)


def get_custom_field_options(field_name: str, connection_account: ConnectionAccount):
    access_token = connection_account.authentication['access_token']
    if field_name == 'project':
        return get_projects_options(access_token)
    raise NotImplementedError('Not implemented')


def get_projects_options(
    access_token: str,
):
    projects = get_projects(access_token)
    return FieldOptionsResponseType(options=linear_map_project_custom_options(projects))


def get_selected_projects(access_token: str, connection_account: ConnectionAccount):
    if not connection_account.settings:
        return []
    selected_projects = connection_account.settings.get('projects', [])
    if 'All Projects Selected' not in selected_projects:
        return selected_projects
    projects = get_projects(access_token)
    connection_account.settings['projects'] = [project['id'] for project in projects]
    connection_account.save()
    return connection_account.settings.get('projects', [])
