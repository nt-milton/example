from typing import Any, Generator

from integration.account import get_integration_laika_objects, integrate_account
from integration.encryption_utils import get_decrypted_or_encrypted_value
from integration.exceptions import ConnectionAlreadyExists
from integration.heroku.constants import INVALID_HEROKU_CREDENTIALS
from integration.heroku.mapper import (
    HEROKU_SYSTEM,
    HerokuRequest,
    _map_user_response_to_laika_object,
)
from integration.heroku.rest_client import get_team_members, get_teams
from integration.models import ConnectionAccount
from integration.store import Mapper, update_laika_objects
from objects.system_types import USER

N_RECORDS = get_integration_laika_objects(HEROKU_SYSTEM)


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        integrate_users(connection_account)
        integrate_account(connection_account, HEROKU_SYSTEM, N_RECORDS)


def connect(connection_account: ConnectionAccount):
    configuration_state = connection_account.configuration_state
    with connection_account.connection_error(error_code=INVALID_HEROKU_CREDENTIALS):
        if 'credentials' in configuration_state:
            api_key = get_api_key(connection_account)
            teams = get_teams(api_key)
            connection_account.authentication['allTeams'] = teams
            configuration_state['allTeams'] = teams
            connection_account.save()


def get_api_key(connection_account):
    return get_decrypted_or_encrypted_value('apiKey', connection_account)


def integrate_users(connection_account: ConnectionAccount):
    api_key = get_api_key(connection_account)
    selected_teams = _get_selected_teams(connection_account)
    teams: list[str] = get_all_or_selected_teams(
        api_key, selected_teams, connection_account
    )
    user_mapper = Mapper(
        map_function=_map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )
    users = _get_users(api_key, teams, connection_account)
    update_laika_objects(connection_account, user_mapper, users)


def get_all_or_selected_teams(
    api_key: str,
    selected_teams: list[str],
    connection_account: ConnectionAccount,
):
    if 'all' in selected_teams:
        teams: list[dict] = get_teams(api_key)
        connection_account.authentication['allTeams'] = teams
        return [team.get('id') for team in teams]
    return connection_account.settings.get('selectedTeams')


def _get_users(
    api_key, teams, connection_account: ConnectionAccount
) -> Generator[HerokuRequest, Any, None]:
    user_objects: list[dict] = []
    all_users: list[dict] = []
    for team in teams:
        team_name = get_team_name(team, connection_account)
        for user in get_team_members(api_key=api_key, team_id=team):
            user_objects.append({'user_data': user, 'team': team_name})
            all_users.append(user)
    yield from get_user_with_teams(all_users, user_objects)


def get_user_with_teams(all_users, user_objects) -> Generator[HerokuRequest, Any, None]:
    user_teams: list[str] = []
    user_roles: set[str] = set()
    for user in all_users:
        user_teams.clear()
        user_roles.clear()
        for user_obj in user_objects:
            user_data = user_obj.get('user_data')
            if user_data.get('user', {}).get('id') == user.get('user').get('id'):
                user_teams.append(user_obj.get('team'))
                user_roles.add(user_data.get('role'))

        yield HerokuRequest(user, user_teams, list(user_roles))


def get_team_name(team_id: str, connection_account: ConnectionAccount) -> str:
    teams = connection_account.authentication.get('allTeams', {})
    for team in teams:
        if team.get('id') == team_id:
            return team.get('name')
    return ''


def raise_if_duplicate(connection_account: ConnectionAccount):
    heroku_connection_accounts: list[
        ConnectionAccount
    ] = ConnectionAccount.objects.filter(
        organization=connection_account.organization,
        integration=connection_account.integration,
    ).exclude(
        id=connection_account.id
    )
    api_key = get_api_key(connection_account)
    selected_teams = _get_selected_teams(connection_account)
    for heroku_connection_account in heroku_connection_accounts:
        connection_teams = _get_selected_teams(heroku_connection_account)
        api_key_decrypted = get_decrypted_or_encrypted_value(
            'apiKey', heroku_connection_account
        )
        if api_key_decrypted == api_key and (
            set(selected_teams) == set(connection_teams)
        ):
            raise ConnectionAlreadyExists()


def _get_selected_teams(connection_account) -> list[str]:
    return connection_account.settings.get('selectedTeams', [])
