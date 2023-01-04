import requests
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

from integration.constants import REQUESTS_TIMEOUT
from integration.exceptions import TimeoutException, TooManyRequests
from integration.jumpcloud.constants import JUMPCLOUD
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import JUMPCLOUD_API_URL

NUMBER_OF_ATTEMPTS = 3

logger_name = __name__

retry_condition = (
    retry_if_exception_type(ConnectionError)
    | retry_if_exception_type(TooManyRequests)
    | retry_if_exception_type(TimeoutException)
)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name=JUMPCLOUD,
        logger_name=logger_name,
        is_generator=is_generator,
    )


def _get_authorization_headers(access_token: str):
    return {'x-api-key': access_token}


@retry(
    stop=stop_after_attempt(NUMBER_OF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_organizations(access_token: str):
    url = f'{JUMPCLOUD_API_URL}/organizations'
    log_request(url, 'get_organizations', logger_name)
    response = requests.get(
        url, headers=_get_authorization_headers(access_token), timeout=REQUESTS_TIMEOUT
    )
    raise_client_exceptions(response=response)
    return response


@retry(
    stop=stop_after_attempt(NUMBER_OF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users(access_token: str, organization_id: str, limit: int, skip: int):
    url = f'{JUMPCLOUD_API_URL}/users?limit={limit}&skip={skip}'
    log_request(url, 'get_users', logger_name)
    response = requests.get(
        url,
        headers={
            'x-org-id': organization_id,
            **_get_authorization_headers(access_token),
        },
        timeout=REQUESTS_TIMEOUT,
    )
    raise_client_exceptions(response=response)
    return response


@retry(
    stop=stop_after_attempt(NUMBER_OF_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_system_users(access_token: str, organization_id: str, limit: int, skip: int):
    url = f'{JUMPCLOUD_API_URL}/systemusers?limit={limit}&skip={skip}'
    log_request(url, 'get_system_users', logger_name)
    response = requests.get(
        url,
        headers={
            'x-org-id': organization_id,
            **_get_authorization_headers(access_token),
        },
        timeout=REQUESTS_TIMEOUT,
    )
    raise_client_exceptions(response=response)
    return response
