import logging
import time
from datetime import datetime
from typing import Union

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.encryption_utils import decrypt_value
from integration.integration_utils.constants import PAGE_SIZE, retry_condition
from integration.log_utils import log_action, log_request
from integration.okta.utils import API_LIMIT
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry

OKTA_ATTEMPTS = 3

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(vendor_name='Okta', logger_name=logger_name, is_generator=is_generator)


def _build_header(credentials: dict) -> dict:
    return dict(Authorization=f"SSWS {decrypt_value(credentials.get('apiToken', ''))}")


def build_okta_api_url(credentials: dict) -> str:
    return f"https://{credentials.get('subdomain')}/api/v1"


def get_okta_users(credentials: dict, **kwargs):
    users_url = f'{build_okta_api_url(credentials)}/users?limit={PAGE_SIZE}'
    return users_generator(users_url, _build_header(credentials), **kwargs)


@retry(
    stop=stop_after_attempt(OKTA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users_by_segment(credentials: dict, user_id: str, okta_segment: str, **kwargs):
    okta_url = f'{build_okta_api_url(credentials)}/users/{user_id}/{okta_segment}'
    log_request(
        okta_url, f'get_users_by_segment: {okta_segment}', logger_name, **kwargs
    )
    response = requests.get(
        okta_url, headers=_build_header(credentials), timeout=REQUESTS_TIMEOUT
    )
    wait_if_api_limit(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()


def wait_if_api_limit(response):
    if response.status_code == 429:
        remaining = response.headers.get('x-rate-limit-remaining')
        requests_remaining = int(remaining)
        limit_reset = response.headers.get('x-rate-limit-reset')
        reset_timestamp = int(limit_reset) + 15
        if requests_remaining in API_LIMIT:
            current_timestamp = int(datetime.now().timestamp())
            wait_time = reset_timestamp - current_timestamp
            if wait_time >= 0:
                time.sleep(wait_time)


@retry(
    stop=stop_after_attempt(OKTA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_groups(credentials: dict):
    groups_url = f'{build_okta_api_url(credentials)}/groups'
    log_request(groups_url, 'get_groups', logger_name)
    response = requests.get(
        groups_url, headers=_build_header(credentials), timeout=REQUESTS_TIMEOUT
    )
    wait_if_api_limit(response)
    raise_client_exceptions(response=response)
    return response.json()


@log_action(**_log_values())
def users_generator(url: str, headers: dict, **kwargs):
    users = []
    users_url: Union[str, None] = url

    @retry(
        stop=stop_after_attempt(OKTA_ATTEMPTS),
        wait=wait_exponential(),
        reraise=True,
        retry=retry_condition,
    )
    def _users_generator(current_url):
        log_request(current_url, 'users_generator', logger_name, **kwargs)
        users_response = requests.get(
            current_url, headers=headers, timeout=REQUESTS_TIMEOUT
        )
        wait_if_api_limit(users_response)
        raise_client_exceptions(response=users_response, **kwargs)

        return users_response

    while users_url:
        response = _users_generator(users_url)

        users += response.json()
        links = response.links
        if 'next' in links:
            users_url = links['next']['url']
        else:
            users_url = None

    return users
