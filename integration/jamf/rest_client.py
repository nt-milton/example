import logging
from collections import namedtuple

from requests.auth import HTTPBasicAuth
from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import JAMF_API_URL
from integration.utils import wait_if_rate_time_api

JAMF_PAG_SIZE = 100

logger_name = __name__
logger = logging.getLogger(logger_name)

JAMF_ATTEMPTS = 3


def _log_values(is_generator: bool = False):
    return dict(vendor_name='Jamf', logger_name=logger_name, is_generator=is_generator)


def _build_headers(access_token: str):
    return {"Authorization": f"Bearer {access_token}"}


@retry(
    stop=stop_after_attempt(JAMF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_computers(access_token: str, next_page: str, subdomain: str, **kwargs):
    url = (
        f'https://{subdomain}.{JAMF_API_URL}/v1/computers-inventory?'
        'section=GENERAL&section=PURCHASING&'
        'section=USER_AND_LOCATION&section=HARDWARE&'
        'section=OPERATING_SYSTEM&'
        'section=DISK_ENCRYPTION&'
        f'page-size={JAMF_PAG_SIZE}&'
        f'page={next_page}&'
        'sort=id:asc'
    )
    log_request(url, 'get_computers', logger_name, **kwargs)
    response = requests.get(
        url=url, headers=_build_headers(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()['results']


@retry(
    stop=stop_after_attempt(JAMF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_mobile_devices(access_token: str, next_page: str, subdomain: str, **kwargs):
    url = (
        f'https://{subdomain}.{JAMF_API_URL}/v2/mobile-devices?'
        f'page-size={JAMF_PAG_SIZE}&'
        f'page={next_page}&'
        'sort=id:asc'
    )
    log_request(url, 'get_mobile_devices', logger_name, **kwargs)
    response = requests.get(
        url=url, headers=_build_headers(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()['results']


@retry(
    stop=stop_after_attempt(JAMF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_mobile_details(access_token: str, mobile_id: str, subdomain: str):
    url = f'https://{subdomain}.{JAMF_API_URL}/v2/mobile-devices/{mobile_id}/detail'
    log_request(url, 'get_mobile_details', logger_name)
    response = requests.get(
        url=url, headers=_build_headers(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


def get_all_devices(access_token, method, subdomain, **kwargs):
    next_page = 0
    has_next = True
    while has_next:
        devices = method(access_token, next_page, subdomain, **kwargs)
        if devices:
            for device in devices:
                yield device
            next_page += 1
        else:
            has_next = False


@retry(
    stop=stop_after_attempt(JAMF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_departments(access_token: str, subdomain: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f'https://{subdomain}.{JAMF_API_URL}/v1/departments'
    log_request(url, 'get_departments', logger_name)
    response = requests.get(url=url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return {
        department['id']: department['name']
        for department in response.json()['results']
    }


@retry(
    stop=stop_after_attempt(JAMF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_buildings(access_token: str, subdomain: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f'https://{subdomain}.{JAMF_API_URL}/v1/buildings'
    log_request(url, 'get_buildings', logger_name)
    response = requests.get(url=url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return {building['id']: building['name'] for building in response.json()['results']}


def get_devices(access_token: str, subdomain: str):
    for computer in get_all_devices(access_token, get_computers, subdomain):
        yield RawDevices(device_type='computer', device=computer)
    for mobile in get_all_devices(access_token, get_mobile_devices, subdomain):
        mobile_device_details = get_mobile_details(
            access_token, mobile['id'], subdomain
        )
        yield RawDevices(device_type='mobile', device=mobile_device_details)


RawDevices = namedtuple('RawDevices', ('device_type', 'device'))


@retry(
    stop=stop_after_attempt(JAMF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_access_token(credential: dict, username: str, password: str):
    subdomain = credential.get('subdomain', '')
    url = f'https://{subdomain}.{JAMF_API_URL}/auth/tokens'
    log_request(url, 'get_access_token', logger_name)
    response = requests.post(
        url=url, auth=HTTPBasicAuth(username, password), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()['token']


@retry(
    stop=stop_after_attempt(JAMF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_auth_info(credential: dict, access_token):
    subdomain = credential.get('subdomain', '')
    url = f'https://{subdomain}.{JAMF_API_URL}/v1/auth'
    log_request(url, 'get_auth_info', logger_name)
    response = requests.get(
        url=url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()
