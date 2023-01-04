import json
import logging
from typing import List, Optional

from integration.store import Mapper, clean_up_by_criteria, update_laika_objects
from integration.utils import (
    calculate_date_range,
    iso_format,
    resolve_laika_object_types,
)
from objects.system_types import (
    ACCOUNT,
    EVENT,
    MONITOR,
    USER,
    resolve_laika_object_type,
)

from ..account import get_integration_laika_objects, integrate_account
from ..encryption_utils import get_decrypted_or_encrypted_value
from ..exceptions import ConnectionAlreadyExists
from ..log_utils import time_metric
from ..models import ConnectionAccount
from ..response_handler.utils import log_metrics
from .constants import INVALID_SENTRY_TOKEN
from .mapper import (
    SentryUser,
    build_map_monitor_response_to_laika_object,
    map_event_response_to_laika_object,
    map_user_response_to_laika_object,
)
from .rest_client import (
    get_monitor_events_and_next_page,
    get_monitors,
    get_organizations_with_projects,
    get_project_events,
    get_projects_by_organization,
    get_teams,
    get_users,
    validate_and_refresh_token,
)

logger = logging.getLogger(__name__)
SENTRY_SYSTEM = 'Sentry'
N_RECORDS = get_integration_laika_objects(SENTRY_SYSTEM)


def run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        raise_if_duplicate(connection_account)
        auth_token = get_auth_token(connection_account)
        organization = connection_account.organization
        resolve_laika_object_types(
            organization=organization,
            laika_object_types=[ACCOUNT, EVENT, MONITOR, USER],
        )
        integrate_users(connection_account, auth_token)
        integrate_monitors(connection_account, auth_token)
        # TODO: remove events code
        integrate_account(connection_account, SENTRY_SYSTEM, N_RECORDS)


def connect(connection_account: ConnectionAccount):
    with connection_account.connection_error(error_code=INVALID_SENTRY_TOKEN):
        if 'credentials' in connection_account.configuration_state:
            auth_token = get_auth_token(connection_account)
            validate_and_refresh_token(auth_token)
            organizations = get_organizations_with_projects(
                auth_token,
            )
            connection_account.configuration_state['organizations'] = organizations


def get_auth_token(connection_account: ConnectionAccount):
    return get_decrypted_or_encrypted_value('authToken', connection_account)


def raise_if_duplicate(connection_account: ConnectionAccount):
    auth_token = get_auth_token(connection_account)
    sentry_connection_accounts: list[
        ConnectionAccount
    ] = ConnectionAccount.objects.filter(
        organization=connection_account.organization,
        integration=connection_account.integration,
    ).exclude(
        id=connection_account.id
    )
    for sentry_connection_account in sentry_connection_accounts:
        auth_token_decrypted = get_decrypted_or_encrypted_value(
            'authToken', sentry_connection_account
        )
        if auth_token_decrypted == auth_token:
            raise ConnectionAlreadyExists()


def get_sentry_users(auth_token, organizations):
    for user in get_users(auth_token, organizations):
        user_is_active = user.get('user', {}).get('isActive', False)
        if user_is_active:
            yield SentryUser(user=user)


def integrate_users(connection_account: ConnectionAccount, auth_token: str):
    organizations = get_selected_organizations(connection_account, auth_token)
    users = get_sentry_users(auth_token, organizations)

    user_mapper = Mapper(
        map_function=map_user_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=USER,
    )

    update_laika_objects(connection_account, user_mapper, users)


def integrate_monitors(connection_account: ConnectionAccount, auth_token: str) -> List:
    projects = get_selected_projects(connection_account, auth_token)
    monitors = get_monitors(auth_token, projects)
    organizations = get_selected_organizations(connection_account, auth_token)
    users = get_sentry_users(auth_token, organizations)
    teams = get_teams(auth_token, organizations)
    monitor_mapper = Mapper(
        map_function=build_map_monitor_response_to_laika_object(list(users), teams),
        keys=['Id'],
        laika_object_spec=MONITOR,
    )

    update_laika_objects(
        connection_account=connection_account,
        mapper=monitor_mapper,
        raw_objects=monitors,
        escape_characters=True,
    )
    return monitors


def _get_cursor_chunks(connection_account: ConnectionAccount) -> int:
    return connection_account.integration.metadata.get('cursor_chunks', 1000)


def integrate_events_v2(connection_account: ConnectionAccount, auth_token: str) -> None:
    projects = get_selected_projects(connection_account, auth_token)
    selected_time_range = calculate_date_range()

    for project in projects:
        chunk_count = 1
        slug = project.get('slug')
        cache = connection_account.authentication.setdefault('cache', {})
        stop_event: str = cache.get(slug)
        delta_event = None
        next_page = None  # First time url is set in internal function
        while True:
            with time_metric('rest_client_get_events'):
                events, next_page = get_project_events(
                    auth_token=auth_token,
                    organization=project.get('organization'),
                    project=slug,
                    selected_time_range=selected_time_range,
                    next_page=next_page,
                )
            if events and not delta_event:
                delta_event = events[0]
            message = (
                f'Storing #{len(events)} events '
                f'in chunk #{chunk_count} for '
                f'project {project}'
            )
            logger.info(f'Connection account {connection_account.id} - {message}')
            _store_issue_events(
                connection_account=connection_account,
                current_events=events,
            )
            log_metrics()
            if not next_page or _reach_stop(events, stop_event):
                break
            chunk_count += 1
        if delta_event:
            cache[slug] = str(delta_event.get('eventID'))
            connection_account.save()
    clean_up_by_criteria(
        connection_account,
        EVENT,
        lookup_query={'data__Event date__gt': iso_format(selected_time_range)},
    )


def _reach_stop(events: list[dict], stop_event: Optional[str]):
    if not stop_event:
        return False
    for evt in events:
        if evt.get('eventID') == stop_event:
            logger.info(f'Delta event found stopping project {stop_event}')
            return True
    return False


def integrate_events(connection_account: ConnectionAccount, auth_token: str) -> None:
    selected_time_range = calculate_date_range()

    for monitor_id in _get_current_monitor_ids(connection_account):
        chunk_count = 1
        next_page = None  # First time url is set in internal function
        while True:
            with time_metric('rest_client_get_events'):
                events, next_page = get_monitor_events_and_next_page(
                    auth_token=auth_token,
                    monitor_id=monitor_id,
                    selected_time_range=selected_time_range,
                    next_page=next_page,
                    next_chunk=chunk_count,
                    cursor_chunks=_get_cursor_chunks(connection_account),
                )
            message = (
                f'Storing #{len(events)} events '
                f'in chunk #{chunk_count} for '
                f'monitor {monitor_id}'
            )
            logger.info(f'Connection account {connection_account.id} - {message}')
            _store_issue_events(
                connection_account=connection_account,
                current_events=events,
            )
            log_metrics()
            if not next_page:
                break
            chunk_count += 1
    clean_up_by_criteria(
        connection_account,
        EVENT,
        lookup_query={'data__Event date__gt': iso_format(selected_time_range)},
    )


def _store_issue_events(
    connection_account: ConnectionAccount,
    current_events: List,
) -> List:
    event_mapper = Mapper(
        map_function=map_event_response_to_laika_object,
        keys=['Id'],
        laika_object_spec=EVENT,
    )
    updated_object_keys = update_laika_objects(
        connection_account=connection_account,
        mapper=event_mapper,
        raw_objects=current_events,
        cleanup_objects=False,
        escape_characters=True,
    )
    return updated_object_keys


def get_selected_projects(
    connection_account: ConnectionAccount, auth_token: str
) -> List:
    is_all_selected = connection_account.settings.get('allProjectsSelected', False)
    if is_all_selected:
        selected_organizations = get_selected_organizations(
            connection_account, auth_token
        )
        all_projects = []
        for organization in selected_organizations:
            projects = get_projects_by_organization(
                organization,
                auth_token,
            )
            all_projects.extend(projects)
        return all_projects
    selected_projects = connection_account.settings.get('selectedProjects', [])
    if selected_projects:
        projects_ready = list(map(lambda p: json.loads(p), selected_projects))
        return projects_ready
    return get_all_projects(auth_token)


def get_selected_organizations(
    connection_account: ConnectionAccount, auth_token: str
) -> List:
    selected_organizations = connection_account.settings.get(
        'selectedOrganizations', []
    )
    if selected_organizations:
        return selected_organizations
    sentry_organizations = get_organizations_with_projects(auth_token)
    organizations = [organization.get('slug') for organization in sentry_organizations]
    return list(organizations)


def get_all_projects(auth_token: str) -> List:
    sentry_organizations = get_organizations_with_projects(auth_token)
    all_projects = []
    for organization in sentry_organizations:
        all_projects.extend(organization.get('projects', []))
    return all_projects


def _get_current_monitor_ids(connection_account: ConnectionAccount) -> List:
    monitor_type = resolve_laika_object_type(
        organization=connection_account.organization, spec=MONITOR
    )
    return connection_account.laika_objects.filter(
        object_type=monitor_type, is_manually_created=False
    ).values_list('data__Id', flat=True)
