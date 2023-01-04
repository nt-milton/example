import logging

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.integration_utils.microsoft_utils import token_header
from integration.log_utils import log_action, log_request
from integration.microsoft.rest_client import HEADERS
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import (
    MICROSOFT_API_URL,
    MICROSOFT_INTUNE_CLIENT_ID,
    MICROSOFT_INTUNE_CLIENT_SECRET,
    MICROSOFT_OAUTH_URL,
)
from integration.utils import wait_if_rate_time_api

logger_name = __name__
logger = logging.getLogger(logger_name)

MICROSOFT_ATTEMPTS = 3

SCOPE = 'https://graph.microsoft.com/DeviceManagementManagedDevices.Read.All'


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='MICROSOFT INTUNE',
        logger_name=logger_name,
        is_generator=is_generator,
    )


def _access_token_data(refresh_token):
    return {
        'grant_type': 'refresh_token',
        'scope': SCOPE,
        'client_secret': MICROSOFT_INTUNE_CLIENT_SECRET,
        'client_id': MICROSOFT_INTUNE_CLIENT_ID,
        'refresh_token': refresh_token,
    }


def _refresh_token_data(code, redirect_uri):
    return {
        'grant_type': 'authorization_code',
        'scope': SCOPE,
        'client_secret': MICROSOFT_INTUNE_CLIENT_SECRET,
        'client_id': MICROSOFT_INTUNE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'code': code,
    }


def create_refresh_token(code: str, redirect_uri: str):
    data = _refresh_token_data(code, redirect_uri)
    url = MICROSOFT_OAUTH_URL
    response = requests.post(url=url, data=data, headers=HEADERS)
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
)
@log_action(**_log_values())
def create_access_token(refresh_token: str) -> tuple[str, str]:
    data = _access_token_data(refresh_token)
    url = MICROSOFT_OAUTH_URL
    log_request(url, 'create_access_token', logger_name)
    response = requests.post(url=url, data=data, headers=HEADERS)
    raise_client_exceptions(response=response)
    return response.json()['access_token'], response.json()['refresh_token']


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
)
@log_action(**_log_values())
def get_managed_devices(access_token: str):
    url = f'{MICROSOFT_API_URL}/deviceManagement/managedDevices'
    log_request(url, 'get_manged_devices', logger_name)
    response = requests.get(url=url, headers=token_header(access_token))
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json().get('value')
