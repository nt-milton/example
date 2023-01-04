from typing import Dict, List

from integration.utils import get_first_last_name
from objects.system_types import ChangeRequest, User

ASANA_SYSTEM = 'Asana'
ASANA_FIELD = 'story'


def map_change_request_response_to_laika_object(ticket, connection_name):
    change = ChangeRequest()
    change.key = ticket.ticket['gid']
    change.title = ticket.ticket['name']
    change.issue_type = ticket.ticket['resource_type']
    change.description = ticket.ticket['notes']
    change.url = ticket.ticket['permalink_url']
    assignee = ticket.ticket['assignee']
    change.assignee = assignee['name'] if assignee else ''
    change.project = format_projects(ticket.ticket['projects'])
    transitions = list(map(map_transitions_from_stories, ticket.stories))
    transitions.sort(key=lambda transition: transition['date'])
    change.transitions_history = {
        'template': CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE,
        'data': transitions or [],
    }
    change.started = ticket.ticket['created_at']
    change.status = 'Done' if ticket.ticket['completed'] else ''
    change.ended = ticket.ticket['completed_at']
    change.source_system = ASANA_SYSTEM
    change.connection_name = connection_name
    return change.data()


def map_transitions_from_stories(stories: Dict):
    return (
        {
            'author': (stories.get('created_by') or {}).get('name'),
            'date': stories['created_at'],
            'field': ASANA_FIELD,
            'details': stories.get('text', ''),
        }
        if stories
        else None
    )


def map_user_response_to_laika_object(user, connection_name):
    organizations = user.get('organizations')
    organization = organizations[0] if organizations else {}
    lo_user = User()
    lo_user.id = user['gid']
    first_name, last_name = get_first_last_name(user['name'])
    lo_user.first_name = first_name
    lo_user.last_name = last_name
    lo_user.title = organization.get('title', '')
    lo_user.email = user['email']
    lo_user.roles = ''
    lo_user.groups = ''
    lo_user.organization_name = organization.get('name', '')
    lo_user.source_system = ASANA_SYSTEM
    lo_user.connection_name = connection_name
    return lo_user.data()


def asana_map_project_custom_options(options_generator: List) -> List:
    projects = []
    for project in options_generator:
        projects.append(
            {
                'id': project.get('gid'),
                'value': {
                    'name': project.get('name', ''),
                    'projectType': project.get('resource_type', ''),
                    'workspaceName': project.get('workspace').get('name'),
                },
            }
        )
    return projects


def format_projects(projects: List):
    projects_names = [project.get('name') for project in projects]
    return ', '.join(projects_names)


CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE = 'asanaTransitionsHistory'
