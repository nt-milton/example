from collections import namedtuple
from typing import Union

from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.exceptions import ConfigurationError, TimeoutException, TooManyRequests
from integration.log_utils import log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.token import TokenProvider
from integration.utils import wait_if_rate_time_api

PAGE_SIZE = 100
MICROSOFT_ATTEMPTS = 3

retry_condition = (
    retry_if_exception_type(ConnectionError)
    | retry_if_exception_type(TooManyRequests)
    | retry_if_exception_type(TimeoutException)
)

GROUP_TYPE = '#microsoft.graph.group'

ROLE_TYPE = '#microsoft.graph.directoryRole'

GLOBAL_ADMIN = 'Global Administrator'

TENANT_ERROR = 'Authentication_RequestFromNonPremiumTenantOrB2CTenant'

MicrosoftRequest = namedtuple(
    'MicrosoftRequest', ('groups', 'user', 'organization', 'roles')
)

ServicePrincipal = namedtuple('ServicePrincipal', ('service', 'roles', 'subscription'))


def token_header(access_token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {access_token}'}


def graph_page_generator(token: Union[str, TokenProvider], endpoint=None):
    @retry(
        stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
        wait=wait_exponential(),
        reraise=True,
        retry=retry_condition,
    )
    def _get_objects_response():
        log_request(endpoint, 'graph_page_generator', __name__)
        access_token = token if isinstance(token, str) else token()
        response = requests.get(
            endpoint,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=REQUESTS_TIMEOUT,
        )
        wait_if_rate_time_api(response)
        raise_client_exceptions(response=response)
        json_data = response.json()
        if 'error' in response:
            raise ConfigurationError.insufficient_permission(response)
        return json_data

    """Generator for paginated result sets returned by Microsoft Graph."""
    while endpoint:
        json_response = _get_objects_response()

        yield from json_response.get('value')
        endpoint = json_response.get('@odata.nextLink')


def map_groups_roles(response):
    memberships = response.get('value', []) if response is not None else []
    groups, roles = [], []
    for membership in memberships:
        if GROUP_TYPE == membership.get('@odata.type'):
            groups.append(membership.get('displayName'))

        elif ROLE_TYPE == membership.get('@odata.type'):
            roles.append(membership.get('displayName'))
    yield groups, roles


def get_device_type(name: str):
    device_name = name.upper()
    return (
        _is_desktop(device_name)
        or _is_mobile(device_name)
        or _is_laptop(device_name)
        or 'Other'
    )


def _is_laptop(device_name: str):
    if (
        'LAPTOP' in device_name
        or 'MACBOOK PRO' in device_name
        or 'MACBOOK AIR' in device_name
    ):
        return 'Laptop'


def _is_mobile(device_name: str):
    if (
        'ANDROID' in device_name
        or 'IPHONE' in device_name
        or 'IPAD' in device_name
        or 'PHONE' in device_name
    ):
        return 'Mobile'


def _is_desktop(device_name: str):
    if 'DESKTOP' in device_name or 'IMAC' in device_name:
        return 'Desktop'
