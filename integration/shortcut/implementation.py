import logging

from integration.store import Mapper, update_laika_objects
from objects.system_types import CHANGE_REQUEST, USER, ChangeRequest, User

from ..account import get_integration_laika_objects, integrate_account
from ..encryption_utils import get_decrypted_or_encrypted_value
from ..exceptions import ConnectionAlreadyExists
from ..models import ConnectionAccount
from ..types import FieldOptionsResponseType
from ..utils import calculate_date_range, get_first_last_name, prefetch
from .constants import INVALID_SHORTCUT_API_KEY
from .rest_client import (
    get_epics,
    get_members,
    get_projects,
    get_workflows,
    get_workflows_states,
    list_change_requests,
)

logger = logging.getLogger(__name__)

SHORTCUT_SYSTEM = 'Shortcut'
SHORTCUT_CHANGE_REQUEST_FIELDS = {
    'epic_id': 'epic',
    'follower_ids': 'followers',
    'iteration_id': 'iteration',
    'label_ids': 'labels',
    'owner_ids': 'owners',
    'project_id': 'project',
    'requested_by_id': 'requester',
    'story_type': 'story type',
    'subject_story_link_ids': 'subject story links',
    'task_ids': 'tasks',
    'workflow_state_id': 'workflow state',
}
CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE = 'shortcutTransitionsHistory'
N_RECORDS = get_integration_laika_objects(SHORTCUT_SYSTEM)


def perform_refresh_token(connection_account: ConnectionAccount):
    api_key = keys(connection_account)
    if not api_key:
        logger.warning(
            f'Error getting keys for {SHORTCUT_SYSTEM} '
            f'connection account {connection_account.id}'
        )


def build_mapper(projects, epics, members, wf_states):
    def map_change_request_to_laika_object(change_request, connection_name):
        lo_change_request = ChangeRequest()
        lo_change_request.key = f'ch{change_request.data["id"]}'
        lo_change_request.title = change_request.data['name']
        lo_change_request.description = change_request.data['description']
        lo_change_request.issue_type = change_request.data['story_type']
        lo_change_request.epic = epics.get(change_request.data['epic_id'])
        lo_change_request.project = projects.get(change_request.data['project_id'])
        owners = [members.get(owner) for owner in change_request.data['owner_ids']]
        lo_change_request.assignee = ', '.join(owners)
        lo_change_request.reporter = members.get(change_request.data['requested_by_id'])
        lo_change_request.status = wf_states.get(
            change_request.data['workflow_state_id']
        )
        transitions, approver = map_raw_transitions_and_approver(
            change_request.histories, members
        )
        lo_change_request.approver = approver
        lo_change_request.transitions_history = {
            'template': CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE,
            'data': transitions or [],
        }
        lo_change_request.started = change_request.data.get('started_at', '')
        lo_change_request.ended = change_request.data.get('completed_at', '')
        lo_change_request.url = change_request.data['app_url']
        lo_change_request.source_system = SHORTCUT_SYSTEM
        lo_change_request.connection_name = connection_name
        return lo_change_request.data()

    return map_change_request_to_laika_object


def build_transition_field_mapper(origin, lookup=None):
    def field_mapper(value):
        if lookup is not None:
            return origin.get(value, {}).get(lookup, value)
        return origin.get(value, value) or 'None'

    return field_mapper


def build_transition(field, values, history, members, references):
    transition = {
        'field': SHORTCUT_CHANGE_REQUEST_FIELDS.get(field, field),
        'author': members.get(history.get('member_id', ''), ''),
        'date': history.get('changed_at', ''),
    }
    if field in ['epic_id', 'iteration_id', 'project_id', 'workflow_state_id']:
        old = values.get('old')
        new = values.get('new')
        transition.update(
            {
                'before': references.get(old, {}).get('name', old) or 'None',
                'after': references.get(new, {}).get('name', new) or 'None',
            }
        )
    elif field in ['follower_ids', 'owner_ids', 'label_ids', 'task_ids']:
        if field in ['follower_ids', 'owner_ids']:
            mapper = build_transition_field_mapper(members)
        if field in ['label_ids', 'task_ids']:
            mapper = build_transition_field_mapper(references, 'name')
        adds = map(mapper, values.get('adds', []))
        removes = map(mapper, values.get('removes', []))
        transition.update({'adds': list(adds), 'removes': list(removes)})
    elif field == 'requested_by_id':
        old = values.get('old')
        new = values.get('new')
        transition.update(
            {
                'before': members.get(old, old) or 'None',
                'after': members.get(new, new) or 'None',
            }
        )
    elif field in ['deadline', 'description', 'name', 'story_type', 'completed']:
        transition.update(
            {
                'before': str(values.get('old')) or 'None',
                'after': str(values.get('new')) or 'None',
            }
        )
    else:
        return None
    return transition


def map_raw_transitions_and_approver(histories, members):
    transitions = []
    approver = ''
    for history in histories:
        references = {
            reference['id']: reference for reference in history.get('references', [])
        }
        for action in history.get('actions', []):
            for field, values in action.get('changes', {}).items():
                if field == 'completed' and values.get('new'):
                    approver = members.get(history.get('member_id', ''), '')
                transition = build_transition(
                    field, values, history, members, references
                )
                if transition:
                    transitions.append(transition)
    transitions.sort(key=lambda transition: transition['date'])
    return transitions, approver


def map_users_to_laika_object(user, connection_name):
    first_name, last_name = get_first_last_name(user['profile']['name'])
    lo_user = User()
    lo_user.id = user['id']
    lo_user.first_name = first_name
    lo_user.last_name = last_name
    lo_user.email = user['profile']['email_address']
    lo_user.is_admin = user['role'] == 'owner'
    lo_user.title = None
    lo_user.organization_name = None
    lo_user.roles = ''
    lo_user.groups = ''
    lo_user.mfa_enabled = user['profile'].get('two_factor_auth_activated')
    lo_user.mfa_enforced = None
    lo_user.source_system = SHORTCUT_SYSTEM
    lo_user.connection_name = connection_name
    return lo_user.data()


def run(connection_account):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        get_decrypted_or_encrypted_value('apiKey', connection_account)
        api_key = keys(connection_account)
        integrate_change_requests(connection_account, api_key=api_key)
        integrate_users(connection_account, api_key)
        integrate_account(connection_account, SHORTCUT_SYSTEM, N_RECORDS)


def connect(connection_account):
    with connection_account.connection_error(error_code=INVALID_SHORTCUT_API_KEY):
        if 'credentials' in connection_account.configuration_state:
            get_decrypted_or_encrypted_value('apiKey', connection_account)
            prefetch(connection_account, 'workflow')


def integrate_change_requests(connection_account: ConnectionAccount, api_key: str):
    # TODO - remove 'project' related code after al
    #  connections_accounts in prod are using workflows.
    selected_workflows = connection_account.settings.get('workflows')
    selected_projects = connection_account.settings.get('projects')
    selected_time_range = calculate_date_range()
    projects = get_projects(api_key)
    epics = get_epics(api_key)
    members = {
        member['id']: member['profile']['mention_name']
        for member in get_members(api_key)
    }
    wf_states = get_workflows_states(api_key)

    change_request_mapper = Mapper(
        map_function=build_mapper(projects, epics, members, wf_states),
        keys=['Key'],
        laika_object_spec=CHANGE_REQUEST,
    )
    if selected_workflows:
        ch_requests = list_change_requests(
            api_key, selected_time_range, selected_workflows=selected_workflows
        )
    if selected_projects:
        ch_requests = list_change_requests(
            api_key, selected_time_range, projects_filter=selected_projects
        )
    update_laika_objects(connection_account, change_request_mapper, ch_requests)


def integrate_users(connection_account: ConnectionAccount, api_key: str):
    user_mapper = Mapper(
        map_function=map_users_to_laika_object, keys=['Id'], laika_object_spec=USER
    )
    users = filter_deactivated_users(get_members(api_key))
    update_laika_objects(connection_account, user_mapper, users)


def filter_deactivated_users(users: list[dict]):
    return [user for user in users if not user.get('disabled')]


def get_custom_field_options(field_name: str, connection_account: ConnectionAccount):
    # TODO - remove 'project' related code after al
    #  connections_accounts in prod are using workflows.
    api_key = keys(connection_account)
    if field_name == 'project':
        projects = get_projects(api_key)
        return _get_project_options(projects)
    if field_name == 'workflow':
        workflows = get_workflows(api_key)
        return _get_workflow_options(workflows)
    else:
        raise NotImplementedError('Not implemented')


def _get_project_options(projects):
    # TODO - Remove This code after al connections_accounts in prod are using workflows.
    project_options = []
    for key, project in projects.items():
        project_options.append({'id': str(key), 'value': {'name': project}})
    return FieldOptionsResponseType(options=project_options)


def _get_workflow_options(workflows: dict):
    workflow_options = []
    for key, workflow in workflows.items():
        workflow_options.append({'id': str(key), 'value': {'name': workflow}})
    return FieldOptionsResponseType(options=workflow_options)


def raise_if_duplicate(connection_account: ConnectionAccount):
    # TODO - Remove This code after al connections_accounts in prod are using workflows.
    projects = connection_account.settings.get('projects')
    if projects:
        exists = (
            ConnectionAccount.objects.actives(
                configuration_state__settings__projects__contains=projects,
                organization=connection_account.organization,
            )
            .exclude(id=connection_account.id)
            .exists()
        )
    workflows = connection_account.settings.get('workflows')
    if workflows:
        exists = (
            ConnectionAccount.objects.actives(
                configuration_state__settings__workflows__contains=workflows,
                organization=connection_account.organization,
            )
            .exclude(id=connection_account.id)
            .exists()
        )
    if exists:
        raise ConnectionAlreadyExists()


def keys(connection_account: ConnectionAccount) -> str:
    credential = connection_account.configuration_state.get('credentials')
    return credential.get('apiKey')
