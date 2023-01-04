from typing import Dict, List, TypedDict

INVALID_CREDENTIALS_OR_LACK_PERMISSIONS_ALERT = '001'


class DatadogUser(TypedDict, total=False):
    id: str
    name: str
    email: str
    role: str
    title: str
    has_2fa: bool
    teams: List
    organization_name: str


class DatadogServiceAccount(TypedDict, total=False):
    id: str
    display_name: str
    description: str
    owner_id: str
    is_active: str
    created_date: str
    email: str
    roles: str
    title: str


def get_page_roles(response_values: Dict) -> Dict:
    filter_roles = list(
        filter(
            lambda included: included.get('type') == 'roles',
            response_values.get('included', []),
        )
    )
    return {ro.get('id'): ro.get('attributes').get('name') for ro in filter_roles}


def get_user_organization_id(user: Dict) -> str:
    return user.get('relationships', {}).get('org', {}).get('data', {}).get('id')


def get_organizations_mapped(organizations: List) -> Dict:
    mapped_organizations: Dict = {}
    if not organizations:
        return mapped_organizations

    for org in organizations:
        public_id = org.get('public_id')
        mapped_organizations[public_id] = org.get('name')

    return mapped_organizations


def create_datadog_user(
    user: Dict,
    organizations: Dict,
    all_roles: Dict,
) -> DatadogUser:
    user_org_id = get_user_organization_id(user=user)
    attributes = user.get('attributes', {})
    user_roles = user.get('relationships', {}).get('roles', {}).get('data', [])
    user_role_ids = [data.get('id') for data in user_roles]

    return DatadogUser(
        id=user.get('id', ''),
        name=attributes.get('name', ''),
        email=attributes.get('email', ''),
        title=attributes.get('title', ''),
        has_2fa=False,
        organization_name=organizations.get(user_org_id, ''),
        teams=[],
        role=', '.join(all_roles.get(role_id, '').title() for role_id in user_role_ids),
    )


def create_datadog_service_account(
    service_account: Dict,
    all_roles: Dict,
) -> DatadogServiceAccount:
    attributes = service_account.get('attributes', {})
    service_account_roles = (
        service_account.get('relationships', {}).get('roles', {}).get('data', [])
    )
    user_role_ids = [data.get('id') for data in service_account_roles]

    return DatadogServiceAccount(
        id=service_account.get('id', ''),
        display_name=attributes.get('name', ''),
        description='',
        owner_id=attributes.get('email', ''),
        is_active=attributes.get('status'),
        created_date=attributes.get('created_at', ''),
        email=attributes.get('email', ''),
        roles=', '.join(
            all_roles.get(role_id, '').title() for role_id in user_role_ids
        ),
        title=attributes.get('title', ''),
    )


MAIL_IDENTIFICATION = '.com'
SLACK_IDENTIFICATION = '@slack'


def build_destinations_and_notification_monitor_data(
    monitor_message: str,
) -> tuple[str, str]:
    emails, slack_channels, other = divide_destinations(monitor_message)
    destinations, notification_types = build_strings(emails, slack_channels, other)
    return destinations, notification_types


def divide_destinations(monitor_message: str) -> tuple[list, list, list]:
    message_values = [
        token for token in monitor_message.split() if token.startswith('@')
    ]
    emails = []
    slack_channels = []
    other = []
    for value in message_values:
        if SLACK_IDENTIFICATION in value:
            slack_channels.append(value)
        elif MAIL_IDENTIFICATION in value:
            emails.append(value[1:])
        else:
            other.append(value)

    return emails, slack_channels, other


def build_strings(emails: list, slack_channels: list, other: list) -> tuple[str, str]:
    destination_items = []
    notification_items = []
    if emails:
        destination_items.append(f'Emails: ({", ".join(emails)})')
        notification_items.append('Email')
    if slack_channels:
        destination_items.append(f'Slack: ({", ".join(slack_channels)})')
        notification_items.append('Slack')
    if other:
        destination_items.append(f'Other: ({", ".join(other)})')
        notification_items.append('Other')

    return ', '.join(destination_items), ', '.join(notification_items)
