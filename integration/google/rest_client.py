import logging
from typing import Dict, List

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.exceptions import ConfigurationError
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request, logger_extra
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import (
    GOOGLE_WORKSPACE_CLIENT_ID,
    GOOGLE_WORKSPACE_CLIENT_SECRET,
    GOOGLE_WORKSPACE_DIRECTORY_API_URL,
    GOOGLE_WORKSPACE_OAUTH_URL,
)
from integration.utils import wait_if_rate_time_api

logger_name = __name__
logger = logging.getLogger(logger_name)

GOOGLE_ATTEMPTS = 3


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Google Workspace',
        logger_name=logger_name,
        is_generator=is_generator,
    )


@retry(
    stop=stop_after_attempt(GOOGLE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_roles(auth_token: str) -> Dict:
    url = f'{GOOGLE_WORKSPACE_DIRECTORY_API_URL}/customer/my_customer/roles'
    log_request(url, 'get_roles', logger_name)
    response = requests.get(
        url, headers={'Authorization': f'Bearer {auth_token}'}, timeout=REQUESTS_TIMEOUT
    )
    items: Dict[str, str] = response.json().get('items', [])

    return (
        {
            items['roleId']: items['roleName'].replace('_', ' ').title()
            for items in response.json()['items']
        }
        if items
        else {}
    )


@retry(
    stop=stop_after_attempt(GOOGLE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_role_assigment(auth_token: str) -> Dict[str, list]:
    url = f'{GOOGLE_WORKSPACE_DIRECTORY_API_URL}/customer/my_customer/roleassignments'
    log_request(url, 'get_role_assigment', logger_name)
    response = requests.get(
        url, headers={'Authorization': f'Bearer {auth_token}'}, timeout=REQUESTS_TIMEOUT
    )

    data = response.json()
    items_list = data.get('items')

    if not items_list:
        return {}

    roles_assigment_list: Dict[str, List] = {}
    for items in data.get('items'):
        if items.get('assignedTo') not in roles_assigment_list:
            roles_assigment_list[items.get('assignedTo')] = []
        roles_assigment_list[items['assignedTo']].append(items.get('roleId'))
    return roles_assigment_list


@retry(
    stop=stop_after_attempt(GOOGLE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users(auth_token: str) -> List:
    try:
        all_users = []
        url = f'{GOOGLE_WORKSPACE_DIRECTORY_API_URL}/users?customer=my_customer'
        response = _user_page_generator(auth_token, url)
        for user in response:
            all_users.append(user)
        return all_users
    except Exception as error:
        logger.warning(logger_extra(f'Error getting users. Error: {error}'))
        raise error


@retry(
    stop=stop_after_attempt(GOOGLE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values(True))
def _user_page_generator(auth_token, url=None):
    default_url = url
    while url:
        log_request(url, 'users_page', logger_name)
        response = requests.get(
            url,
            headers={'Authorization': f'Bearer {auth_token}'},
            timeout=REQUESTS_TIMEOUT,
        )
        wait_if_rate_time_api(response)
        raise_client_exceptions(response=response)
        if not response.json().get('users'):
            logger.info(
                'The users page does not contains '
                f'users key in the json response: {response.json()}'
            )
            return []
        json_response = response.json()
        yield from json_response['users']
        if json_response.get('nextPageToken'):
            next_token = json_response.get('nextPageToken')
            url = f'{default_url}&pageToken={next_token}'
        else:
            url = None


@retry(
    stop=stop_after_attempt(GOOGLE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_tokens(user_id, auth_token):
    url = f'{GOOGLE_WORKSPACE_DIRECTORY_API_URL}/users/{user_id}/tokens'
    log_request(url, 'get_tokens', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    connection_result = raise_client_exceptions(
        response=response, raise_exception=False
    )

    if connection_result.status_code != '200':
        message = f'Not access to get tokens for user id: {user_id}'
        logger.info(logger_extra(message))

    return response.json()


@retry(
    stop=stop_after_attempt(GOOGLE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_organizations(auth_token):
    url = f'{GOOGLE_WORKSPACE_DIRECTORY_API_URL}/customer/my_customer/orgunits?type=all'
    log_request(url, 'get_organizations', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    result = raise_client_exceptions(response=response, raise_exception=False)
    json_response = response.json()
    error = {}
    if result.with_error() and result.status_code == '401':
        raise ConfigurationError.insufficient_permission()

    if result.with_error() and result.status_code == '403':
        response_error = json_response.get('error', {})
        error['message'] = response_error.get('message', '')
        error['code'] = response_error.get('code', '')

    return json_response.get('organizationUnits', []), error


@retry(
    stop=stop_after_attempt(GOOGLE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_access_token(refresh_token):
    data = {
        'grant_type': 'refresh_token',
        'client_secret': GOOGLE_WORKSPACE_CLIENT_SECRET,
        'client_id': GOOGLE_WORKSPACE_CLIENT_ID,
        'refresh_token': refresh_token,
    }
    url = GOOGLE_WORKSPACE_OAUTH_URL
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    log_request(url, 'create_access_token', logger_name)
    response = requests.post(
        url=url, data=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()['access_token']


@retry(
    stop=stop_after_attempt(GOOGLE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_refresh_token(code, redirect_uri):
    data = {
        'grant_type': 'authorization_code',
        'client_secret': GOOGLE_WORKSPACE_CLIENT_SECRET,
        'client_id': GOOGLE_WORKSPACE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    url = GOOGLE_WORKSPACE_OAUTH_URL
    log_request(url, 'create_refresh_token', logger_name)
    response = requests.post(
        url=url, data=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()
