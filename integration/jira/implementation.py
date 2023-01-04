import logging
from datetime import datetime, timezone
from typing import Callable, Dict, Generator, List, Union

import jwt

import integration.integration_utils.token_utils as token_utils
from integration.settings import ATLASSIAN_ACCOUNT_CLAIM
from integration.utils import calculate_date_range, get_first_last_name, prefetch
from objects.models import LaikaObject
from objects.system_types import (
    CHANGE_REQUEST,
    USER,
    ChangeRequest,
    User,
    resolve_laika_object_type,
)

from ..account import get_integration_laika_objects, integrate_account
from ..encryption_utils import get_decrypted_or_encrypted_auth_value
from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..log_utils import logger_extra
from ..models import ConnectionAccount
from ..store import Mapper, update_laika_objects
from ..token import update_tokens
from ..types import FieldOptionsResponseType
from .constants import INSUFFICIENT_ADMINISTRATOR_PERMISSIONS
from .rest_client import (
    accessible_resources,
    create_access_token,
    create_refresh_token,
    get_all_groups,
    get_all_users_by_group,
    get_all_users_data,
    get_fields,
    get_report_account,
    get_tickets_page,
    validate_status_project,
)
from .utils import get_paginated_response_by_api_method, get_projects, validate

REPORT_ACCOUNT = 'report_account'
JIRA_SYSTEM = 'Jira'
DEV_RESOURCE = 'ecosystem'
CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE = 'jiraTransitionsHistory'
N_RECORDS = get_integration_laika_objects(JIRA_SYSTEM)
GROUP_SCOPE = 'read:group:jira'

logger = logging.getLogger(__name__)


def _get_reporter_name(fields):
    if not fields.get('reporter'):
        return ''
    return fields['reporter'].get('displayName', '')


def callback(code, redirect_uri, connection_account):
    if not code:
        raise ConfigurationError.denial_of_consent()

    response = create_refresh_token(code, redirect_uri)
    resources = accessible_resources(response['access_token'])
    response['resources'] = [
        resource for resource in resources if DEV_RESOURCE != resource['name']
    ]
    connection_account.authentication = response
    with connection_account.connection_error(
        error_code=INSUFFICIENT_ADMINISTRATOR_PERMISSIONS
    ):
        projects = validate(response, connection_account)
        organization = connection_account.organization
        resolve_laika_object_type(organization, CHANGE_REQUEST)
        jira_project_prefetch(connection_account, projects)
        connection_account.save()
        return connection_account


def run(connection_account):
    run_by_lo_types(connection_account, [])


def run_by_lo_types(connection_account: ConnectionAccount, lo_types: list[str]):
    with connection_account.connection_attempt():
        deleted = delete_if_close_account(connection_account)
        if deleted:
            return
        raise_if_duplicate(connection_account)
        fetch_token = token_utils.build_fetch_token(connection_account)
        resources = connection_account.authentication['resources']
        raise_if_non_access_projects(connection_account, resources, fetch_token)

        scopes = connection_account.authentication.get('scope', '')
        if 'read:jira-user' in scopes:
            integrate_users(connection_account, fetch_token, resources)
        if not lo_types:
            integrate_change_requests(connection_account)
            connection_account.authentication[REPORT_ACCOUNT] = report_account(
                fetch_token()
            )
            connection_account.save()
        integrate_account(connection_account, JIRA_SYSTEM, N_RECORDS)


def integrate_users(connection_account, fetch_token, resources):
    users = get_user_response_by_api_method(
        api_method=get_all_users_data,
        resources=resources,
        fetch_token=fetch_token,
    )

    if GROUP_SCOPE in connection_account.authentication.get('scope', ''):
        users = get_users_groups(
            resources=resources,
            fetch_token=fetch_token,
            users=list(users),
        )

    mapper = Mapper(
        map_function=map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )

    users = list(users)

    logger.info(logger_extra(f'Users retrieved {len(users)}'))

    update_laika_objects(connection_account, mapper, users)


def integrate_change_requests(connection_account: ConnectionAccount):
    resources = connection_account.authentication['resources']
    selected_time_range = calculate_date_range()
    cloud_projects = connection_account.settings['cloud_projects']

    fetch_token = token_utils.build_fetch_token(connection_account)
    tickets = get_tickets(
        resources,
        fetch_token,
        selected_time_range,
        cloud_projects,
    )
    epic_field = epic_field_key(connection_account, fetch_token())
    mapper = Mapper(
        map_function=build_map_change_requests(epic_field),
        keys=['Key'],
        laika_object_spec=CHANGE_REQUEST,
    )
    logger.info(logger_extra(f'{len(tickets)} tickets retrieved'))
    update_laika_objects(connection_account, mapper, tickets)


def report_account(access_token):
    account = jwt.decode(access_token, verify=False)[ATLASSIAN_ACCOUNT_CLAIM]
    return {"accountId": account, "updatedAt": datetime.now(timezone.utc).isoformat()}


def delete_if_close_account(connection_account: ConnectionAccount):
    account = connection_account.authentication.get(REPORT_ACCOUNT)
    if not account:
        return False

    update_tokens(connection_account, create_access_token)
    account_action = get_report_account(
        account,
        get_decrypted_or_encrypted_auth_value(connection_account),
    )
    if account_action and account_action['status'] == 'closed':
        laika_object_type = resolve_laika_object_type(
            connection_account.organization, CHANGE_REQUEST
        )
        LaikaObject.objects.filter(object_type=laika_object_type).delete()
        connection_account.delete()
        return True

    return False


def get_tickets(
    resources,
    fetch_token,
    since_date,
    filtered_projects: dict,
    ids_only=False,
) -> list:
    filters = dict(date_range_filter=since_date)
    if ids_only:
        filters['fields'] = ['key', 'updated']
    tickets = []
    for resource in resources:
        cloud_id = resource.get('id', '')
        if filtered_projects.get(cloud_id):
            filters['jira_projects'] = filtered_projects[cloud_id]
            tickets.extend(
                list(
                    get_paginated_response_by_api_method(
                        get_tickets_page, cloud_id, fetch_token, **filters
                    )
                )
            )
    return tickets


def get_users_groups(
    resources: List[Dict],
    users: List,
    fetch_token: Callable,
) -> Generator:
    groups_by_user: Dict[str, List] = {}
    for resource in resources:
        cloud_id = resource.get('id', '')
        groups = get_all_groups(cloud_id, fetch_token())
        for group in groups:
            users_by_group = get_all_users_by_group(
                group_id=group.get('groupId', ''),
                cloud_id=cloud_id,
                auth_token=fetch_token(),
            )
            for user in users_by_group:
                account_id = user.get('accountId', '')
                if account_id not in groups_by_user:
                    groups_by_user[account_id] = []
                groups_by_user[account_id].append(group['name'])

    for user in users:
        account_id = user.get('accountId', '')
        user['groups'] = groups_by_user.get(account_id, [])
        yield user


def get_user_response_by_api_method(
    api_method: Callable, resources: List[Dict], fetch_token: Callable, **kwargs
):
    for resource in resources:
        cloud_id = resource['id']
        response = api_method(cloud_id, fetch_token(), **kwargs)
        for item in response:
            yield item


def parse_paragraphs(paragraphs):
    for paragraph in paragraphs:
        for paragraph_line in paragraph.get('content', []):
            if paragraph_line['type'] == 'text':
                yield paragraph_line['text']


def flatten_ticket_description(description: Union[str, dict]):
    if description is None:
        return ''
    if isinstance(description, str):
        return description
    paragraphs = parse_paragraphs(description.get('content', []))
    return '\n'.join(paragraphs)


def map_user_response_to_laika_object(user, connection_name):
    organizations = user.get('organizations')
    organization = organizations[0] if organizations else {}
    lo_user = User()
    lo_user.id = user['accountId']
    display_name = user.get('displayName', '')
    first_name, last_name = get_first_last_name(display_name)
    lo_user.first_name = first_name
    lo_user.last_name = last_name
    lo_user.organization_name = organization.get('name', '')
    lo_user.roles = ''
    lo_user.groups = ''
    lo_user.source_system = JIRA_SYSTEM
    lo_user.connection_name = connection_name
    lo_user.email = user.get('emailAddress', '')
    lo_user.groups = ', '.join(user.get('groups', []))
    return lo_user.data()


def build_map_change_requests(epic_field):
    def map_change_requests_response_to_laika_object(ticket, connection_name):
        fields = ticket.get('fields', {})
        assignee = fields.get('assignee')
        assignee = assignee if assignee else {'displayName': ''}
        started, ended, approver, transitions = process_transitions(ticket)
        change = ChangeRequest()
        change.key = ticket['key']
        change.title = fields['summary']
        change.description = flatten_ticket_description(fields.get('description'))
        change.issue_type = fields['issuetype']['name']
        change.status = fields['status']['name']
        change.project = fields['project']['name']
        change.assignee = assignee['displayName']
        change.reporter = _get_reporter_name(fields)
        change.approver = approver
        change.started = started
        change.transitions_history = {
            'template': CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE,
            'data': transitions or [],
        }
        change.ended = ended
        change.url = ticket['self']
        change.source_system = JIRA_SYSTEM
        change.connection_name = connection_name
        if epic_field:
            change.epic = fields.get(epic_field)
        return change.data()

    return map_change_requests_response_to_laika_object


def process_transitions(ticket):
    transitions = get_transitions_from_ticket(ticket)
    started = None
    ended = None
    approver = None
    for transition in transitions:
        if transition['field'] == 'status':
            if transition['after'] == 'In Progress':
                started = transition['date']
            if transition['after'] == 'Done':
                ended = transition['date']
                approver = transition['author']
    return started, ended, approver, transitions


def get_transitions_from_ticket(ticket):
    fields = ticket.get('fields', {})
    histories = ticket.get('changelog', {'histories': []})['histories']
    transitions = []
    if fields:
        transitions.append(_get_creation_event(fields))
    for history in histories:
        for item in history['items']:
            if item['field'] in ['assignee', 'status']:
                new_transition = _get_transition_from_history_item(item, history)
                transitions.append(new_transition)
    transitions.sort(key=lambda transition: transition['date'])
    return transitions


def _get_transition_from_history_item(item, history):
    return {
        'author': history.get('author', {}).get('displayName'),
        'field': item['field'],
        'date': history['created'],
        'before': item['fromString'] or 'None',
        'after': item['toString'] or 'None',
    }


def _get_creation_event(fields):
    if fields:
        return {
            'author': _get_reporter_name(fields),
            'field': 'created',
            'date': fields['created'],
        }


def raise_if_duplicate(connection_account):
    resources = connection_account.authentication['resources']
    exists = (
        ConnectionAccount.objects.actives(
            authentication__resources=resources,
            organization=connection_account.organization,
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def raise_if_non_access_projects(
    connection_account: ConnectionAccount, resources: list, fetch_token
) -> None:
    selected_projects = _get_selected_projects(
        connection_account, resources, fetch_token
    )
    cloud_projects = {}
    auth_token = fetch_token()
    for resource in resources:
        cloud_id = resource['id']
        cloud_projects[cloud_id] = filter_by_cloud_id(
            selected_projects, cloud_id, auth_token
        )
    detect_missing_projects(cloud_projects, selected_projects)
    connection_account.settings['cloud_projects'] = cloud_projects
    connection_account.save()


def detect_missing_projects(cloud_projects: dict, selected_projects: list):
    all_projects = [project for cp in cloud_projects.values() for project in cp]
    for selected_project in selected_projects:
        if selected_project not in all_projects:
            raise ConfigurationError.not_found()


def filter_by_cloud_id(selected_projects: list, cloud_id: str, auth_token) -> list:
    filtered_projects = []
    for project in selected_projects:
        if validate_status_project(cloud_id, project, auth_token):
            filtered_projects.append(project)
    return filtered_projects


def get_custom_field_options(field_name, connection_account):
    resources = connection_account.authentication['resources']
    if field_name == 'project':
        return get_projects_options(
            resources,
            token_utils.build_fetch_token(connection_account),
        )
    else:
        raise NotImplementedError('Not implemented')


def get_projects_options(resources, fetch_token):
    projects_generator = get_projects(resources, fetch_token)
    projects = jira_map_project_custom_options(projects_generator)
    return FieldOptionsResponseType(options=projects)


def jira_map_project_custom_options(options):
    selected_projects = []
    for project in options:
        selected_projects.append(
            {
                'id': f'{project["key"]}-{project["id"]}-{project["name"]}',
                'value': {
                    'name': project['name'],
                    'projectType': project['projectTypeKey'],
                },
            }
        )
    return selected_projects


def jira_project_prefetch(connection_account, projects):
    if len(projects) > 0:
        options = jira_map_project_custom_options(projects)
        prefetch(connection_account, 'project', options=options)


def epic_field_key(connection_account: ConnectionAccount, token: str):
    resources = connection_account.authentication['resources']
    for resource in resources:
        cloud_id = resource['id']
        response = get_fields(cloud_id, token)
        for item in response:
            if item['name'] == 'Epic Link':
                return item['key']
    return None


def _get_selected_projects(
    connection_account: ConnectionAccount, resources, fetch_token
):
    if not connection_account.settings:
        return []
    projects = connection_account.settings.get('projects', [])
    if 'All Projects Selected' not in projects:
        return [project.split('-')[0] for project in projects]
    projects = get_projects(resources, fetch_token)
    connection_account.settings['projects'] = [
        f'{project["key"]}-{project["id"]}-{project["name"]}' for project in projects
    ]
    connection_account.save()
    return [
        project.split('-')[0]
        for project in connection_account.settings.get('projects', [])
    ]
