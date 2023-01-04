import logging
from collections import namedtuple
from typing import Any, Dict, Union

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import (
    ASANA_API_ENDPOINT,
    ASANA_CLIENT_ID,
    ASANA_CLIENT_SECRET_ID,
    ASANA_OAUTH_URL,
)
from integration.token import TokenProvider
from integration.utils import wait_if_rate_time_api

logger_name = __name__
logger = logging.getLogger(logger_name)

ASANA_ATTEMPTS = 3
PAGE_LIMIT = 100
AsanaTicket = namedtuple('AsanaTicket', ('ticket', 'stories'))


def _log_values(is_generator: bool = False):
    return dict(vendor_name='Asana', logger_name=logger_name, is_generator=is_generator)


def get_json_header(auth_token):
    return {'Authorization': f'Bearer {auth_token}', 'Accept': 'application/json'}


@retry(
    stop=stop_after_attempt(ASANA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_refresh_token(code, redirect_uri):
    data = {
        'grant_type': 'authorization_code',
        'client_secret': ASANA_CLIENT_SECRET_ID,
        'client_id': ASANA_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    url = ASANA_OAUTH_URL
    log_request(url, 'create_refresh_token', logger_name)
    response = requests.post(url=url, data=data, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(ASANA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_access_token(refresh_token):
    data = {
        'grant_type': 'refresh_token',
        'client_secret': ASANA_CLIENT_SECRET_ID,
        'client_id': ASANA_CLIENT_ID,
        'refresh_token': refresh_token,
    }
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    url = ASANA_OAUTH_URL
    log_request(url, 'create_access_token', logger_name)
    response = requests.post(
        url=url, data=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json().get('access_token'), response.json().get('refresh_token')


def get_users(access_token: str, workspace: str):
    opt_fields = 'opt_fields=gid,resource_type,name,email,photo,workspaces'
    params = f'workspace={workspace}&limit={PAGE_LIMIT}'
    url = f'{ASANA_API_ENDPOINT}/users?{opt_fields}&{params}'
    users = _get_paginated_asana_objects(url, access_token)
    return users


@retry(
    stop=stop_after_attempt(ASANA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_projects(auth_token):
    headers = get_json_header(auth_token)
    opt_fields = 'opt_fields=gid,resource_type,name,workspace'
    url = f'{ASANA_API_ENDPOINT}/projects?{opt_fields}'
    log_request(url, 'get_projects', logger_name)
    response = requests.get(url=url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True)
    return response.json().get('data')


@retry(
    stop=stop_after_attempt(ASANA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_workspaces(auth_token):
    headers = get_json_header(auth_token)
    url = f'{ASANA_API_ENDPOINT}/workspaces?limit={PAGE_LIMIT}'
    log_request(url, 'get_workspaces', logger_name)
    response = requests.get(url=url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True)
    return response.json().get('data')


@retry(
    stop=stop_after_attempt(ASANA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def validate_status_project(auth_token: str, project_id: str) -> None:
    headers = get_json_header(auth_token)
    url = f'{ASANA_API_ENDPOINT}/projects/{project_id}'
    log_request(url, 'validate_status_project', logger_name)
    response = requests.get(url=url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    merged_kwargs: Dict[Any, Any] = {**dict(vendor='Asana')}
    raise_client_exceptions(response=response, **merged_kwargs)


def get_tickets(token_provider: TokenProvider, project, selected_time_range):
    opt_fields = (
        'opt_fields=gid,name,start_on,'
        'completed,completed_at,projects.name,'
        'assignee.name,created_at,resource_type,notes,'
        'permalink_url'
    )
    params = (
        f'project={project}&modified_since={selected_time_range}&limit={PAGE_LIMIT}'
    )
    url = f'{ASANA_API_ENDPOINT}/tasks?{opt_fields}&{params}'
    while url:
        data, url = get_tickets_by_page(url, token_provider)
        for ticket in data:
            info = AsanaTicket(
                ticket=ticket, stories=get_ticket_story(ticket['gid'], token_provider)
            )
            yield info


@retry(
    stop=stop_after_attempt(ASANA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_tickets_by_page(url, token: Union[str, TokenProvider]):
    log_request(url, 'get_tickets_by_page', logger_name)
    response = requests.get(
        url, headers=get_json_header(get_valid_token(token)), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    data = response.json().get('data')
    next_page = response.json().get('next_page')
    if next_page:
        url = next_page.get('uri')
    else:
        url = None
    return data, url


def get_ticket_story(ticket_id: str, token: Union[str, TokenProvider]):
    url = f'{ASANA_API_ENDPOINT}/tasks/{ticket_id}/stories?limit={PAGE_LIMIT}'
    stories = _get_paginated_asana_objects(url, token)
    return list(stories)


@retry(
    stop=stop_after_attempt(ASANA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
def execute_paginated_call(token: Union[str, TokenProvider], current_url: str):
    headers = get_json_header(get_valid_token(token))
    log_request(current_url, 'asana_request', logger_name)
    response = requests.get(url=current_url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True)
    response_json = response.json()
    data = response_json.get('data')
    next_page = response_json.get('next_page')
    if next_page:
        url = next_page.get('uri')
    else:
        url = None
    return data, url


def _get_paginated_asana_objects(
    url: Union[str, None], token: Union[str, TokenProvider]
):
    while url:
        response_data, url = execute_paginated_call(token, url)

        for element in response_data:
            yield element


def get_valid_token(token: Union[str, TokenProvider]):
    return token if isinstance(token, str) else token()
