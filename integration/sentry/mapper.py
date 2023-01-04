from collections import namedtuple

from objects.system_types import Event, Monitor, User

SENTRY_SYSTEM = 'Sentry'


def name_formatted(full_name: str) -> dict[str, str]:
    composed_name = {'first_name': '', 'last_name': ''}
    if full_name:
        names = full_name.split(' ')
        if len(names) > 2:
            composed_name['first_name'] = names[0]
            composed_name['last_name'] = f'{names[1]} {names[2]}'
        elif len(names) == 2:
            composed_name['first_name'] = names[0]
            composed_name['last_name'] = names[1]
        else:
            composed_name['first_name'] = names[0]
    return composed_name


# =================
# USER
# =================
SentryUser = namedtuple('SentryUser', ('user',))


def map_user_response_to_laika_object(sentry_user, connection_name):
    lo_user = User()
    user_object = sentry_user.user.get('user', {})
    lo_user.id = user_object.get('id')
    lo_user.first_name = name_formatted(sentry_user.user['name']).get('first_name', '')
    lo_user.last_name = name_formatted(sentry_user.user['name']).get('last_name', '')
    lo_user.email = sentry_user.user['email']
    lo_user.roles = sentry_user.user['role']
    lo_user.is_admin = user_object.get('isSuperuser', False)
    lo_user.organization_name = sentry_user.user['name']
    lo_user.groups = ','.join(sentry_user.user.get('projects', []))
    lo_user.mfa_enabled = user_object.get('has2fa', False)
    lo_user.source_system = SENTRY_SYSTEM
    lo_user.connection_name = connection_name
    return lo_user.data()


# =================
# MONITOR
# =================
SentryMonitor = namedtuple('SentryMonitor', ('monitor',))


def get_name_attr(keys):
    return ', '.join([i.get('name') for i in keys])


def build_query_field(sentry_monitor):
    conditions = get_name_attr(sentry_monitor.get('conditions', []))
    filters = get_name_attr(sentry_monitor.get('filters', []))
    actions = get_name_attr(sentry_monitor.get('actions', []))
    action_match = sentry_monitor.get('actionMatch')
    filter_match = sentry_monitor.get('filterMatch')
    when_text = f'when {action_match}  ({conditions})' if conditions else ''
    if_text = f'if {filter_match} ({filters})' if filters else ''
    then_text = f'then {actions}' if actions else ''
    return f'{when_text} {if_text} {then_text}'


def build_notification_type_field(sentry_monitor):
    notification_type = {
        'NotifyEmailAction': 'Email',
        'NotifyEventAction': 'In-App Notification',
        'SlackNotifyServiceAction': 'Slack',
    }
    actions = sentry_monitor.get('actions', [])
    return ', '.join(
        {
            notification_type.get(action['id'].split('.')[-1], 'Other')
            for action in actions
        }
    )


def get_user_email(user_id, users):
    for user in users:
        if str(user_id) == str(user.user['user']['id']):
            return user.user['email']
    return ''


def get_team_slug(team_id, teams):
    for team in teams:
        if str(team_id) == str(team['id']):
            return team['slug']
    return ''


def get_display_value(key, value, users, teams):
    if key == 'Member':
        return get_user_email(value, users)
    if key == 'Team':
        return get_team_slug(value, teams)
    return value


def add_key_to_dict(init_dict, key, value, users, teams):
    display_value = get_display_value(key, value, users, teams)
    key = 'Email' if key == 'Member' else key
    if key in init_dict.keys():
        init_dict[key].append(display_value)
    else:
        init_dict[key] = [display_value]


def get_destination_groups(actions, users, teams):
    actions_groups = {}
    for action in actions:
        target_type = action.get('targetType', '')
        target_identifier = action.get('targetIdentifier', '')
        channel = action.get('channel', '')
        action_id = action.get('id', '')
        if channel and 'SlackNotifyServiceAction' in action_id:
            key = 'Slack'
            value = channel
        elif target_type:
            key = target_type
            value = str(target_identifier)
        else:
            continue
        add_key_to_dict(actions_groups, key, value, users, teams)
    return actions_groups


def build_destination_field(sentry_monitor, users, teams):
    actions = sentry_monitor.get('actions', [])
    destination_groups = get_destination_groups(actions, users, teams)
    response = []
    for key, values in destination_groups.items():
        nested_values = ', '.join(values)
        response.append(f'{key}{f": ({nested_values})" if any(values) else ""}')
    return ', '.join(response)


def build_map_monitor_response_to_laika_object(users, teams):
    def map_monitor_response_to_laika_object(sentry_monitor, connection_name):
        lo_monitor = Monitor()
        lo_monitor.id = str(sentry_monitor.get('id'))
        lo_monitor.name = sentry_monitor.get('name', '')
        lo_monitor.type = sentry_monitor.get('type', '')
        lo_monitor.query = build_query_field(sentry_monitor)
        lo_monitor.created_at = sentry_monitor.get('dateCreated')
        created_by = sentry_monitor.get('createdBy', {})
        lo_monitor.created_by_name = created_by.get('name') if created_by else ''
        lo_monitor.created_by_email = created_by.get('email') if created_by else ''
        lo_monitor.notification_type = build_notification_type_field(sentry_monitor)
        lo_monitor.destination = build_destination_field(sentry_monitor, users, teams)
        lo_monitor.connection_name = connection_name
        lo_monitor.source_system = SENTRY_SYSTEM
        return lo_monitor.data()

    return map_monitor_response_to_laika_object


# =================
# EVENT
# =================
SentryEvent = namedtuple('SentryEvent', ('event',))


def get_tag_list(tag: dict) -> str:
    return tag.get('value', '')


def map_event_response_to_laika_object(sentry_event, connection_name):
    lo_event = Event()
    lo_event.id = str(sentry_event.get('eventID'))
    lo_event.title = sentry_event.get('title', '')
    lo_event.text = sentry_event.get('message', '')
    lo_event.type = sentry_event.get('event.type')
    lo_event.host = sentry_event.get('location', '')
    lo_event.source = sentry_event.get('platform', '')
    lo_event.event_date = sentry_event.get('dateCreated')
    lo_event.tags = ', '.join(map(get_tag_list, sentry_event.get('tags')))
    lo_event.source_system = SENTRY_SYSTEM
    lo_event.connection_name = connection_name
    return lo_event.data()
