import logging
from typing import List

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.azure.utils import (
    ERROR_APP_ID,
    ERROR_OBJECT_ID,
    GRAPH,
    handle_azure_error,
)
from integration.constants import REQUESTS_TIMEOUT
from integration.encryption_utils import decrypt_value
from integration.exceptions import ConfigurationError
from integration.integration_utils.constants import retry_condition
from integration.integration_utils.microsoft_utils import (
    PAGE_SIZE,
    graph_page_generator,
)
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import MICROSOFT_API_URL
from integration.utils import wait_if_rate_time_api

DEFAULT_URL = 'https://login.microsoftonline.com/'
DEFAULT_SCOPES_GRAPH = 'https://graph.microsoft.com/.default'
DEFAULT_SCOPES_AZURE = 'https://management.azure.com/.default'
MICROSOFT_AZURE_API_URL = 'https://management.azure.com'
SUBSCRIPTION_API_VERSION = 'api-version=2021-04-01-preview'
ROLE_API_VERSION = 'api-version=2018-07-01'
TYPE = 'client_credentials'
PASSWORD_CREDENTIALS = 'passwordCredentials'


logger_name = __name__
logger = logging.getLogger(logger_name)

AZURE_ATTEMPTS = 3


def _log_values(is_generator: bool = False):
    return dict(vendor_name='Azure', logger_name=logger_name, is_generator=is_generator)


@retry(
    stop=stop_after_attempt(AZURE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_access_token(credentials, token_type=None):
    tenant_id = credentials.get('tenantId')
    client_id = credentials.get('clientId')
    client_secret = decrypt_value(credentials.get('clientSecret'))
    scope_type = DEFAULT_SCOPES_GRAPH if token_type == GRAPH else DEFAULT_SCOPES_AZURE

    url = f'{DEFAULT_URL}/{tenant_id}/oauth2/v2.0/token'
    log_request(url, 'get_access_token', logger_name)
    response_obj = requests.post(
        url=url,
        data={
            'grant_type': TYPE,
            'scope': scope_type,
            'client_id': client_id,
            'client_secret': client_secret,
        },
        timeout=REQUESTS_TIMEOUT,
    )
    response = response_obj.json()
    wait_if_rate_time_api(response_obj)
    if 'error' in response:
        raise ConfigurationError.bad_client_credentials(response)

    return response


def get_users_filtered(access_token: str, roles: List):
    endpoint = f'{MICROSOFT_API_URL}/users?$top={PAGE_SIZE}'
    users = graph_page_generator(access_token, endpoint)

    for user in users:
        groups = get_user_groups(access_token, user['id'])
        user['groups'] = ', '.join([group.get('displayName', '') for group in groups])
        for role in roles:
            if user['id'] == role['id']:
                yield role, user


def get_user_groups(access_token: str, user_id: str) -> List:
    url = (
        f'{MICROSOFT_API_URL}/users/{user_id}/memberOf'
        '/microsoft.graph.group?$select=displayName'
    )
    response = requests.get(
        url=url, headers={'Authorization': f'Bearer {access_token}'}
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json().get('value', [])


@retry(
    stop=stop_after_attempt(AZURE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users_from_subscription_role(access_token: str, subscription_id: str) -> list:
    url = (
        f'{MICROSOFT_AZURE_API_URL}/subscriptions/{subscription_id}'
        '/providers/Microsoft.Authorization'
        f'/roleAssignments?{SUBSCRIPTION_API_VERSION}'
    )

    log_request(url, 'get_users_from_subscription_role', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json().get('value', [])


@retry(
    stop=stop_after_attempt(AZURE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_role_definitions(access_token: str, subscription_id: str):
    url = (
        f'{MICROSOFT_AZURE_API_URL}/subscriptions/{subscription_id}'
        '/providers/Microsoft.Authorization'
        f'/roleDefinitions?{ROLE_API_VERSION}'
    )
    log_request(url, 'get_role_definitions', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json().get('value', [])


@retry(
    stop=stop_after_attempt(AZURE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_organization(access_token: str):
    url = f'{MICROSOFT_API_URL}/organization?$select=displayName'
    log_request(url, 'get_organization', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json().get('value')


@retry(
    stop=stop_after_attempt(AZURE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_application_secret_expiration(access_token: str, credentials: dict):
    client_id = credentials.get('clientId')
    url = f"{MICROSOFT_API_URL}/applications?$filter=appId eq '{client_id}'"
    log_request(url, 'get_application_secret_expiration', logger_name)
    response_obj = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    response = response_obj.json()
    wait_if_rate_time_api(response_obj)
    handle_azure_error(response=response, message=ERROR_APP_ID)
    return response


@retry(
    stop=stop_after_attempt(AZURE_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_service_principal_by_app(access_token: str, credentials: dict):
    client_id = credentials.get('clientId')
    object_id = credentials.get('objectId')
    url = (
        f"{MICROSOFT_API_URL}/servicePrincipals?"
        f"$filter=Id eq '{object_id}' and appId eq '{client_id}'"
    )
    log_request(url, 'get_service_principal_by_app', logger_name)
    response_obj = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    response = response_obj.json()
    wait_if_rate_time_api(response_obj)
    handle_azure_error(response=response, message=ERROR_OBJECT_ID)


def get_service_principals(access_token: str, roles: list):
    endpoint = f'{MICROSOFT_API_URL}/servicePrincipals?$top={PAGE_SIZE}'
    service_principals = graph_page_generator(access_token, endpoint)
    for service_principal in service_principals:
        for role in roles:
            if service_principal['id'] == role['id']:
                yield role, service_principal
