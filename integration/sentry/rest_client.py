import logging
from http import HTTPStatus
from typing import List, Tuple, Union

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request, logger_extra
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.sentry.utils import (
    are_all_events_within_date_range,
    can_continue_fetching,
    extract_relevant_events,
    get_mapped_projects,
    has_reached_url_chunks_limit,
    pagination_next_page,
)
from integration.utils import wait_if_rate_time_api

SENTRY_API_URL = 'https://sentry.io/api/0'
SENTRY_ATTEMPTS = 3
SENTRY_PAGE_SIZE = 100

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Sentry', logger_name=logger_name, is_generator=is_generator
    )


def get_sentry_headers(auth_token):
    return {'Authorization': f'Bearer {auth_token}'}


@retry(
    stop=stop_after_attempt(SENTRY_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def validate_and_refresh_token(auth_token: str):
    url = f'{SENTRY_API_URL}/'
    log_request(url, 'validate_and_refresh_token', logger_name)
    response = requests.get(
        url, headers=get_sentry_headers(auth_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.status_code == requests.codes.ok


@log_action(**_log_values())
def get_organizations_with_projects(auth_token: str):
    organizations_url = f'{SENTRY_API_URL}/organizations/'
    organizations = []

    all_organizations = _get_sentry_objects(
        organizations_url,
        auth_token,
    )

    for organization in all_organizations:
        org_id = organization.get('slug')
        projects = get_projects_by_organization(
            org_id,
            auth_token,
        )
        org_data = dict(
            id=organization.get('id', ''),
            name=organization.get('name', ''),
            slug=organization.get('slug', ''),
            projects=projects,
        )
        organizations.append(org_data)

    return organizations


@log_action(**_log_values())
def get_projects_by_organization(org_id: str, auth_token: str):
    url = f'{SENTRY_API_URL}/organizations/'
    projects_url = f"{url}{org_id}/projects/"
    org_projects = _get_sentry_objects(
        projects_url,
        auth_token,
    )
    return get_mapped_projects(org_projects, org_id)


@log_action(**_log_values())
def get_users(auth_token: str, organizations: list):
    users = []

    def _get_all_users():
        for organization in organizations:
            url = f"{SENTRY_API_URL}/organizations/{organization}/users/"
            organization_users = _get_sentry_objects(url, auth_token)

            for organization_user in organization_users:
                yield organization_user

    for user in _get_all_users():
        users.append(user)
    return users


@log_action(**_log_values())
def get_teams(auth_token: str, organizations: list):
    def _get_all_teams():
        for organization in organizations:
            url = f'{SENTRY_API_URL}/organizations/{organization}/teams/'
            organization_teams = _get_sentry_objects(url, auth_token)
            for organization_team in organization_teams:
                yield organization_team

    return list(_get_all_teams())


@log_action(**_log_values())
def get_project_events(
    auth_token: str,
    organization: str,
    project: str,
    selected_time_range: str,
    next_page: Union[str, None] = None,
) -> Tuple[list, Union[str, None]]:
    initial_url = f"{SENTRY_API_URL}/projects/{organization}/{project}/events/"
    next_page = next_page if next_page else initial_url

    events_response = execute_api_call(
        auth_token=auth_token,
        current_url=next_page,
    )
    if not events_response:
        next_page = None
        return [], next_page
    next_page = pagination_next_page(events_response)
    page_events = events_response.json()
    all_events_within_range: bool = are_all_events_within_date_range(
        selected_time_range=selected_time_range, page_events=page_events
    )
    if not all_events_within_range:
        page_events = extract_relevant_events(
            selected_time_range=selected_time_range, current_events=page_events
        )
        next_page = None

    return page_events, next_page


@log_action(**_log_values())
def get_monitor_events_and_next_page(
    auth_token: str,
    monitor_id: str,
    selected_time_range: str,
    cursor_chunks: int,
    next_page: Union[str, None] = None,
    next_chunk: int = 1,
) -> Tuple[List, Union[str, None]]:
    initial_url = f"{SENTRY_API_URL}/issues/{monitor_id}/events/"
    return get_events_and_next_page(
        auth_token,
        initial_url,
        selected_time_range,
        cursor_chunks,
        next_page,
        next_chunk,
    )


@log_action(**_log_values())
def get_events_and_next_page(
    auth_token: str,
    initial_url: str,
    selected_time_range: str,
    cursor_chunks: int,
    next_page: Union[str, None] = None,
    next_chunk: int = 1,
) -> Tuple[List, Union[str, None]]:
    events = []
    reached_chunks_limit = False
    next_page = next_page if next_page else initial_url
    chunks_limit = next_chunk * cursor_chunks

    while can_continue_fetching(reached_chunks_limit, next_page):
        events_response = execute_api_call(
            auth_token=auth_token,
            current_url=next_page,
        )
        if not events_response:
            next_page = None
            return [], next_page

        next_page = pagination_next_page(events_response)
        reached_chunks_limit = has_reached_url_chunks_limit(
            current_url=next_page, chunks_limit=chunks_limit
        )

        page_events = events_response.json()
        all_events_within_range: bool = are_all_events_within_date_range(
            selected_time_range=selected_time_range, page_events=page_events
        )
        if not all_events_within_range:
            page_events = extract_relevant_events(
                selected_time_range=selected_time_range, current_events=page_events
            )
            next_page = None

        for event in page_events:
            events.append(event)

    return events, next_page


@log_action(**_log_values())
def get_monitors(auth_token: str, projects: list):
    monitors = []

    def _get_all_monitors():
        for project in projects:
            url = (
                f"{SENTRY_API_URL}/organizations"
                f"/{project.get('organization')}"
                f"/combined-rules/?project={project.get('id')}"
            )
            project_monitors = _get_sentry_objects(url, auth_token)

            for project_monitor in project_monitors:
                yield project_monitor

    for monitor in _get_all_monitors():
        monitors.append(monitor)

    return monitors


@retry(
    stop=stop_after_attempt(SENTRY_ATTEMPTS),
    wait=wait_exponential(multiplier=3),
    reraise=True,
    retry=retry_condition,
)
def execute_api_call(
    auth_token: str,
    current_url: str,
):
    log_request(current_url, 'sentry_objects', logger_name)
    objects_response = requests.get(
        url=current_url,
        headers=get_sentry_headers(auth_token),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(objects_response)
    result = raise_client_exceptions(
        raise_exception=False,
        response=objects_response,
    )
    if int(result.status_code) == HTTPStatus.NOT_FOUND:
        message = f'Resource not found for URL: {current_url}'
        logger.warning(logger_extra(message))
        return None

    return objects_response


def _get_sentry_objects(url: str, auth_token: str):
    while True:
        response = execute_api_call(auth_token, url)

        if not response:
            break

        for element in response.json():
            yield element

        next_page = pagination_next_page(response)
        if next_page:
            url = next_page
        else:
            break
