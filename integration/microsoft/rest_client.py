import logging
from http import HTTPStatus

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.integration_utils.microsoft_utils import (
    MICROSOFT_ATTEMPTS,
    PAGE_SIZE,
    TENANT_ERROR,
    graph_page_generator,
    map_groups_roles,
    token_header,
)
from integration.log_utils import log_action, log_request, logger_extra
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import (
    MICROSOFT_API_URL,
    MICROSOFT_CLIENT_ID,
    MICROSOFT_CLIENT_SECRET,
    MICROSOFT_OAUTH_URL,
)
from integration.token import TokenProvider
from integration.utils import wait_if_rate_time_api

MICROSOFT_365 = 'Microsoft 365'

SCOPE = (
    'https://graph.microsoft.com/Directory.Read.All '
    'https://graph.microsoft.com/GroupMember.Read.All '
    'https://graph.microsoft.com/User.Read.All '
    'https://graph.microsoft.com/AuditLog.Read.All'
)
HEADERS = {
    'content-type': 'application/x-www-form-urlencoded',
}

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name=MICROSOFT_365, logger_name=logger_name, is_generator=is_generator
    )


@log_action(**_log_values())
def create_refresh_token(code: str, redirect_uri: str):
    data = {
        'grant_type': 'authorization_code',
        'scope': SCOPE,
        'client_secret': MICROSOFT_CLIENT_SECRET,
        'client_id': MICROSOFT_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    url = MICROSOFT_OAUTH_URL
    log_request(url, 'create_refresh_token', logger_name)
    response = requests.post(
        url=url, data=data, headers=HEADERS, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@log_action(**_log_values())
def create_access_token(refresh_token: str) -> tuple[str, str]:
    data = {
        'grant_type': 'refresh_token',
        'scope': SCOPE,
        'client_secret': MICROSOFT_CLIENT_SECRET,
        'client_id': MICROSOFT_CLIENT_ID,
        'refresh_token': refresh_token,
    }
    url = MICROSOFT_OAUTH_URL
    log_request(url, 'create_access_token', logger_name)
    response = requests.post(
        url=url, data=data, headers=HEADERS, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()['access_token'], response.json()['refresh_token']


@log_action(**_log_values(True))
def get_users_by_group(access_token: str, group_id: str):
    url = f'{MICROSOFT_API_URL}/groups/{group_id}/members?$top={PAGE_SIZE}'
    users = graph_page_generator(access_token, url)

    for user in users:
        groups_tuple = get_memberships_by_user(access_token, user['id'])
        for groups, roles in groups_tuple:
            yield groups, user, roles


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_groups(access_token: str):
    url = f'{MICROSOFT_API_URL}/groups?$select=id,displayName'
    log_request(url, 'get_groups', logger_name)
    response = requests.get(
        url=url, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json().get('value')


@log_action(**_log_values())
def get_sign_ins_names(token_provider: TokenProvider, delta: str):
    is_valid = _is_valid_tenant(token_provider())
    if not is_valid:
        return []

    base_url = f'{MICROSOFT_API_URL}/auditLogs/signIns?$top={PAGE_SIZE}'
    endpoint = base_url + f'&$filter=createdDateTime gt {delta}' if delta else base_url
    return graph_page_generator(token_provider, endpoint)


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_devices(access_token: str):
    url = f'{MICROSOFT_API_URL}/devices?$expand=registeredOwners'
    log_request(url, 'get_org_devices', logger_name)
    response = requests.get(
        url=url, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json().get('value')


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values(True))
def get_memberships_by_user(access_token: str, user_id: str):
    url = f'{MICROSOFT_API_URL}/users/{user_id}/memberOf?$select=displayName,type'

    log_request(url, 'get_memberships_by_user', logger_name)
    response = requests.get(
        url=url, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    connection_result = raise_client_exceptions(
        response=response, raise_exception=False
    )
    if int(connection_result.status_code) == HTTPStatus.NOT_FOUND:
        message = f'Resource not found for user id: {user_id}'
        logger.info(logger_extra(message))
    json_response = response.json()
    yield from map_groups_roles(json_response)


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_organization(access_token: str):
    url = f'{MICROSOFT_API_URL}/organization?$select=displayName'
    log_request(url, 'get_organization', logger_name)
    response = requests.get(
        url, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json().get('value')


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _is_valid_tenant(access_token: str):
    endpoint = f'{MICROSOFT_API_URL}/auditLogs/signIns?$top={1}'
    log_request(endpoint, '_is_valid_tenant', logger_name)
    response = requests.get(
        endpoint, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    res = response.json()
    if 'error' in res and res.get('error').get('code') == TENANT_ERROR:
        logger.info(f'Tenant is invalid, premium license is required. {res}')
        return False
    return True
