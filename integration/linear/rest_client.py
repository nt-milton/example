import logging
import time
from datetime import datetime
from typing import Dict

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.linear.queries import (
    get_issue_query,
    projects_query,
    users_query,
    viewer_query,
)
from integration.log_utils import log_action, log_request, logger_extra
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import (
    LINEAR_API_URL,
    LINEAR_CLIENT_ID,
    LINEAR_CLIENT_SECRET,
    LINEAR_OAUTH_URL,
)
from integration.utils import validate_graphql_connection_error
from objects.utils import build_bearer_header

API_LIMIT = 1

LINEAR_ATTEMPTS = 3

APOLLO_ERRORS = [
    'GRAPHQL_PARSE_FAILED',
    'INPUT_ERROR',
    'GRAPHQL_VALIDATION_FAILED',
    'BAD_USER_INPUT',
]

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Linear', logger_name=logger_name, is_generator=is_generator
    )


@retry(
    stop=stop_after_attempt(LINEAR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users(access_token: str):
    log_request(LINEAR_API_URL, 'get_users', logger_name)
    response = requests.post(
        LINEAR_API_URL,
        json={'query': users_query},
        headers=build_bearer_header(access_token),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_api_limit(response)
    raise_client_exceptions(response=response, is_graph_api=True)
    data = response.json()
    return data['data']['users']['nodes']


@log_action(**_log_values(True))
def get_issues(access_token: str, selected_projects: list):
    @retry(
        stop=stop_after_attempt(LINEAR_ATTEMPTS),
        wait=wait_exponential(),
        reraise=True,
        retry=retry_condition,
    )
    def _get_issue_response(query):
        log_request(LINEAR_API_URL, 'get_issue', logger_name)
        return requests.post(
            LINEAR_API_URL,
            json={'query': query},
            headers=build_bearer_header(access_token),
            timeout=REQUESTS_TIMEOUT,
        )

    for project in selected_projects:
        has_next = True
        issues_params = "(first:100)"
        while has_next:
            issue_query = get_issue_query(issues_params, project)
            response = _get_issue_response(issue_query)
            wait_if_api_limit(response)
            data = response.json()
            if not data:
                logger.info(f'the response is empty or None:{data}')
                return {}
            if has_invalid_data(data):
                has_next = False
                issues_params = "(first:100)"
                message = logger_extra(f'Linear Graphql API Error -> message: {data}')
                logger.info(message)
            else:
                issues = data['data']['project']['issues']
                has_next = issues['pageInfo']['hasNextPage']
                end_cursor = issues['pageInfo']['endCursor']
                issues_params = f"(first:100, after:{end_cursor})"
                for issues in issues['nodes']:
                    yield issues


@retry(
    stop=stop_after_attempt(LINEAR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_projects(access_token: str):
    log_request(LINEAR_API_URL, 'get_projects', logger_name)
    response = requests.post(
        LINEAR_API_URL,
        json={'query': projects_query},
        headers=build_bearer_header(access_token),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_api_limit(response)
    raise_client_exceptions(response=response, is_graph_api=True)
    data = response.json()
    validate_graphql_connection_error(response, data)
    return data['data']['projects']['nodes']


@retry(
    stop=stop_after_attempt(LINEAR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_current_user(access_token: str):
    log_request(LINEAR_API_URL, 'get_current_user', logger_name)
    response = requests.post(
        LINEAR_API_URL,
        json={'query': viewer_query},
        headers=build_bearer_header(access_token),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_api_limit(response)
    raise_client_exceptions(response=response, is_graph_api=True)
    data = response.json()
    return data['data']['viewer']


@retry(
    stop=stop_after_attempt(LINEAR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_access_token(code: str, redirect_uri: str):
    params = {
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': LINEAR_CLIENT_ID,
        'client_secret': LINEAR_CLIENT_SECRET,
        'grant_type': 'authorization_code',
    }
    header = {'Content-Type': 'application/x-www-form-urlencoded'}
    log_request(LINEAR_OAUTH_URL, 'get_access_token', logger_name)
    response = requests.post(
        LINEAR_OAUTH_URL, data=params, headers=header, timeout=REQUESTS_TIMEOUT
    )
    wait_if_api_limit(response)
    raise_client_exceptions(response=response)
    return response.json()


def wait_if_api_limit(response):
    requests_remaining = int(response.headers.get('X-RateLimit-Requests-Remaining', 1))
    reset_timestamp = int(response.headers.get('X-RateLimit-Requests-Reset', 0)) + 15
    if requests_remaining == API_LIMIT:
        current_timestamp = int(datetime.now().timestamp())
        wait_time = reset_timestamp - current_timestamp
        if wait_time >= 0:
            time.sleep(wait_time)


def has_invalid_data(data: Dict) -> bool:
    return (
        'errors' in data
        and data.get('errors', [])[0].get('extensions', {}).get('code') in APOLLO_ERRORS
    )
