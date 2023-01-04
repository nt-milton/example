from datetime import datetime
from typing import List, TypedDict

from integration.datadog.utils import build_destinations_and_notification_monitor_data
from integration.integration_utils.mapping_utils import get_user_name_values
from objects.system_types import Event, Monitor, ServiceAccount, User

DATADOG_SYSTEM = 'Datadog'


class DatadogData(TypedDict, total=False):
    included: List
    data: List


def map_monitor_response_to_laika_object(monitor, connection_name):
    destinations, notification_type = build_destinations_and_notification_monitor_data(
        monitor.get('message', '')
    )
    lo_monitor = Monitor()
    lo_monitor.id = str(monitor['id'])
    lo_monitor.name = monitor['name']
    lo_monitor.type = monitor['type']
    lo_monitor.query = monitor['query']
    lo_monitor.tags = ','.join(monitor.get('tags', []))
    lo_monitor.message = monitor['message']
    lo_monitor.overall_state = monitor['overall_state']
    lo_monitor.created_at = monitor['created']
    lo_monitor.created_by_name = monitor['creator']['name']
    lo_monitor.created_by_email = monitor['creator']['email']
    lo_monitor.notification_type = notification_type
    lo_monitor.destination = destinations
    lo_monitor.source_system = DATADOG_SYSTEM
    lo_monitor.connection_name = connection_name
    return lo_monitor.data()


def map_event_response_to_laika_object(event, connection_name):
    lo_event = Event()
    lo_event.id = str(event['id'])
    lo_event.title = event['title']
    lo_event.text = event['text']
    lo_event.type = event['alert_type']
    lo_event.tags = ','.join(event.get('tags', []))
    lo_event.priority = event['priority']
    lo_event.host = event['host']
    lo_event.device = event['device_name']
    lo_event.source = event['source']
    lo_event.event_date = datetime.fromtimestamp(event['date_happened']).isoformat()
    lo_event.source_system = DATADOG_SYSTEM
    lo_event.connection_name = connection_name
    return lo_event.data()


def map_users_response_to_laika_object(datadog_user, connection_name):
    ADMIN_USER = 'datadog admin role'

    user_lo = User()
    user_lo.id = datadog_user.get('id', '')
    user_name: List[str] = get_user_name_values(datadog_user.get('name', ''))
    user_lo.first_name = user_name[0]
    user_lo.last_name = user_name[1]
    user_lo.email = datadog_user.get('email', '')
    user_role: str = datadog_user.get('role', '')
    user_lo.is_admin = ADMIN_USER in user_role.lower()
    user_lo.title = datadog_user.get('title', '')
    user_lo.organization_name = datadog_user.get('organization_name', '')
    user_lo.roles = user_role
    teams = (
        ', '.join(team for team in datadog_user.get('teams'))
        if datadog_user.get('teams')
        else ''
    )
    user_lo.groups = teams
    user_lo.mfa_enabled = datadog_user.get('has_2fa', False)
    user_lo.mfa_enforced = ''
    user_lo.source_system = DATADOG_SYSTEM
    user_lo.connection_name = connection_name
    return user_lo.data()


def map_service_account_to_laika_object(service_account, connection_name):
    lo_service_account = ServiceAccount()
    lo_service_account.id = service_account.get('id', '')
    lo_service_account.display_name = service_account.get('display_name', '')
    lo_service_account.description = service_account.get('description')
    lo_service_account.owner_id = service_account.get('owner_id')
    lo_service_account.email = service_account.get('email', '')
    lo_service_account.created_date = service_account.get('created_date', '')
    lo_service_account.is_active = service_account.get('is_active') == 'Active'
    lo_service_account.roles = service_account.get('roles', '')
    lo_service_account.connection_name = connection_name
    lo_service_account.source_system = DATADOG_SYSTEM
    return lo_service_account.data()
