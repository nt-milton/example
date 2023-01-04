import base64
import logging

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import (
    RIPPLING_API_URL,
    RIPPLING_CLIENT_ID,
    RIPPLING_CLIENT_SECRET,
    RIPPLING_DEVICE_WAIT,
    RIPPLING_OAUTH_URL,
)
from integration.utils import wait_if_rate_time_api

BASIC_TOKEN = f'{RIPPLING_CLIENT_ID}:{RIPPLING_CLIENT_SECRET}'
RIPPLING_ATTEMPTS = 3
RIPPLING_BRIDGE_URI = 'http://localhost:88/integration/rippling/callback/'

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Rippling', logger_name=logger_name, is_generator=is_generator
    )


@retry(
    stop=stop_after_attempt(RIPPLING_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_employees(auth_token: str):
    url = f'{RIPPLING_API_URL}/employees'
    log_request(url, 'get_employees', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True)
    return response.json()


@retry(
    stop=stop_after_attempt(RIPPLING_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_company(auth_token: str, **kwargs):
    url = f'{RIPPLING_API_URL}/companies/current'
    log_request(url, 'get_company', logger_name, **kwargs)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True, **kwargs)
    return response.json()


@retry(
    stop=stop_after_attempt(RIPPLING_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_report_request_id(auth_token: str, **kwargs):
    data = {'report_name': 'inventory'}
    url = f'{RIPPLING_API_URL}/reports/report_data'
    log_request(url, 'get_report_request_id', logger_name, **kwargs)
    response = requests.post(
        url=url,
        data=data,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True, **kwargs)
    data = response.json()
    return data.get('request_id', '')


def get_devices_report(auth_token, **kwargs):
    request_id = get_report_request_id(auth_token, **kwargs)
    return attempt_devices_report(auth_token, request_id, **kwargs)


@retry(
    stop=stop_after_attempt(RIPPLING_ATTEMPTS),
    wait=wait_exponential(multiplier=int(RIPPLING_DEVICE_WAIT)),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def attempt_devices_report(auth_token: str, request_id: str, **kwargs):
    url = f'{RIPPLING_API_URL}/reports/report_data?request_id={request_id}'
    log_request(url, 'attempt_devices_report', logger_name, **kwargs)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True, **kwargs)
    report = response.json()
    if 'status' in report:
        raise ConnectionError(
            f'Rippling report not ready {response.status_code} {report}'
        )
    devices_report = report.get('Computer inventory report', None)
    return devices_report if devices_report else []


@retry(
    stop=stop_after_attempt(RIPPLING_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_access_token(refresh_token: str, **kwargs):
    data = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
    base64_token = base64.b64encode(BASIC_TOKEN.encode()).decode()
    headers = {'Authorization': f'Basic {base64_token}'}
    url = RIPPLING_OAUTH_URL
    log_request(url, 'create_access_token', logger_name, **kwargs)
    response = requests.post(
        url=url, data=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True, **kwargs)
    data = response.json()
    return data.get('access_token', ''), data.get('refresh_token', '')


@retry(
    stop=stop_after_attempt(RIPPLING_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_refresh_token(code: str, redirect_uri: str, **kwargs):
    url = RIPPLING_OAUTH_URL
    uri = RIPPLING_BRIDGE_URI if 'sandbox' in url else redirect_uri
    data = {'grant_type': 'authorization_code', 'redirect_uri': uri, 'code': code}
    token_bytes = BASIC_TOKEN.encode('ascii')
    base64_bytes = base64.b64encode(token_bytes)
    base64_token = base64_bytes.decode('ascii')
    headers = {'Authorization': f'Basic {base64_token}'}
    log_request(url, 'create_refresh_token', logger_name, **kwargs)
    response = requests.post(
        url=url, data=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()


@retry(
    stop=stop_after_attempt(RIPPLING_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_current_user(auth_token: str, **kwargs):
    url = f'{RIPPLING_API_URL}/me'
    log_request(url, 'get_current_user', logger_name, **kwargs)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True, **kwargs)
    return response.json()
