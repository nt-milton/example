from integration.utils import get_first_last_name
from objects.system_types import ChangeRequest, User

LINEAR_SYSTEM = 'Linear'


def map_change_request_response_to_laika_object(issue, connection_name):
    change = ChangeRequest()
    change.key = issue.get('id')
    change.title = issue.get('title')
    change.description = issue.get('description')
    change.epic = issue.get('identifier')
    project = issue.get('project')
    change.project = project.get('name') if project else ''
    assignee = issue.get('assignee')
    change.assignee = assignee['name'] if assignee else ''
    creator = issue.get('creator')
    change.reporter = creator['name'] if creator else ''
    state = issue.get('state')
    change.status = state['name'] if state else ''
    change.started = issue.get('startedAt')
    change.url = issue.get('url')
    change.source_system = LINEAR_SYSTEM
    change.connection_name = connection_name
    return change.data()


def map_users_response_to_laika_object(user, connection_name):
    lo_user = User()
    lo_user.id = user['id']
    first_name, last_name = get_first_last_name(user['name'])
    lo_user.first_name = first_name
    lo_user.last_name = last_name
    lo_user.is_admin = user['admin']
    organization = user['organization']
    lo_user.organization_name = organization['name'] if organization else ''
    lo_user.email = user['email']
    lo_user.source_system = LINEAR_SYSTEM
    lo_user.connection_name = connection_name
    return lo_user.data()
