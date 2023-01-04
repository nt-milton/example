import logging
from typing import Dict, List

from django.db.models.query import QuerySet

from integration.account import get_integration_laika_objects, integrate_account
from integration.models import SUCCESS, ConnectionAccount
from integration.store import Mapper, update_laika_objects
from objects.system_types import USER

from ..exceptions import ConfigurationError, ConnectionAlreadyExists
from ..log_utils import connection_data
from ..types import SlackChannelsType
from .mapper import map_users_to_laika_object
from .rest_client import (
    fetch_access_token,
    get_all_slack_channels,
    get_all_slack_users,
    send_slack_message,
)
from .types import SLACK_ALERT_TYPES
from .utils import SLACK_ALERTS_TEMPLATE

logger = logging.getLogger(__name__)

SLACK_SYSTEM = 'Slack'
N_RECORDS = get_integration_laika_objects(SLACK_SYSTEM)


def perform_refresh_token(connection_account: ConnectionAccount):
    access_token = get_access_token(connection_account)
    if not access_token:
        logger.warning(
            f'Error getting token for {SLACK_SYSTEM} '
            f'connection account {connection_account.id}'
        )


def callback(
    code: str, redirect_uri: str, connection_account: ConnectionAccount
) -> ConnectionAccount:
    if not code:
        raise ConfigurationError.denial_of_consent()

    data = connection_data(connection_account)
    response = fetch_access_token(code, redirect_uri, **data)
    access_token = str(response.get('access_token', ''))
    channels = get_all_slack_channels(access_token, **data)
    connection_account.configuration_state['channels'] = list(channels)
    connection_account.authentication = response
    connection_account.save()
    return connection_account


def run(connection_account: ConnectionAccount) -> None:
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        access_token = get_access_token(connection_account)
        integrate_users(connection_account, access_token)
        integrate_account(connection_account, SLACK_SYSTEM, N_RECORDS)


def get_access_token(connection_account: ConnectionAccount) -> str:
    access_token = connection_account.authentication.get('access_token', None)
    if not access_token:
        raise ConfigurationError.bad_client_credentials()
    return access_token


def integrate_users(connection_account: ConnectionAccount, access_token: str) -> None:
    data = connection_data(connection_account)
    user_mapper = Mapper(
        map_function=map_users_to_laika_object, keys=['Id'], laika_object_spec=USER
    )
    users = get_all_slack_users(access_token, **data)
    update_laika_objects(connection_account, user_mapper, users)


def raise_if_duplicate(connection_account: ConnectionAccount) -> None:
    team = connection_account.authentication.get('team', {})
    exists = (
        ConnectionAccount.objects.actives(
            authentication__team=team, organization=connection_account.organization
        )
        .exclude(id=connection_account.id)
        .exists()
    )
    if exists:
        raise ConnectionAlreadyExists()


def get_slack_channels(connection_account: ConnectionAccount) -> SlackChannelsType:
    data = connection_data(connection_account)
    access_token = connection_account.authentication.get('access_token')
    channels = get_all_slack_channels(access_token, **data)
    return SlackChannelsType(channels=channels)


def send_alert_to_slack(alert):
    alert_type = alert.alert_type
    receiver = alert.receiver
    if alert_type in SLACK_ALERTS_TEMPLATE and receiver:
        organization = receiver.organization
        slack_connections = ConnectionAccount.objects.filter(
            organization=organization, integration__vendor__name__iexact=SLACK_SYSTEM
        )
        targets = get_slack_targets(slack_connections, alert_type)
        for channel_id in targets:
            message = SLACK_ALERTS_TEMPLATE[alert_type].get('message_parser')(alert)
            access_token = targets.get(channel_id, {}).get('access_token')
            send_slack_message(access_token, channel_id, message)


def _get_success_connections(slack_connections: QuerySet):
    return filter(lambda conn: conn.status == SUCCESS, slack_connections)


def get_slack_targets(slack_connections: QuerySet, alert_type: str) -> Dict:
    targets: Dict[str, Dict[str, str]] = {}
    success_connections = _get_success_connections(slack_connections)
    for connection in success_connections:
        settings = connection.configuration_state.get('settings', {}).get(
            'notificationPreferences', []
        )
        targets = add_channels_to_targets(settings, targets, alert_type, connection)
    return targets


def add_channels_to_targets(
    settings: List, targets: Dict, alert_type: str, connection: ConnectionAccount
) -> Dict:
    slack_alert_type = SLACK_ALERT_TYPES[alert_type]

    def filter_settings(current_setting: Dict):
        return (
            current_setting.get('type') == slack_alert_type
            and current_setting.get('isEnable')
            and current_setting.get('channel')
        )

    applicable_settings = filter(filter_settings, settings)
    for setting in applicable_settings:
        channel_id = setting.get('channel')
        if channel_id in targets:
            continue

        targets[channel_id] = {
            'channel_id': channel_id,
            'access_token': connection.authentication.get('access_token'),
        }
    return targets
