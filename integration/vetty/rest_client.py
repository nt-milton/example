import logging

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.utils import wait_if_rate_time_api

VETTY_API_URL = 'https://api.vetty.co/cfapi/v1'
VETTY_PAGE_SIZE = 100
VETTY_ATTEMPTS = 3

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(vendor_name='Vetty', logger_name=logger_name, is_generator=is_generator)


def get_headers(api_key: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {api_key}'}


def get_applicants(api_key: str):
    current_page = 0
    has_next = True
    while has_next:
        applicants_response = get_applicants_per_page(api_key, current_page)
        for applicant in applicants_response['content']:
            yield applicant

        has_next = not applicants_response['last']
        current_page += 1


@retry(
    stop=stop_after_attempt(VETTY_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_applicants_per_page(api_key: str, next_page: int):
    url = f'{VETTY_API_URL}/applicants?page={next_page}&size={VETTY_PAGE_SIZE}'
    log_request(url, 'get_applicants_per_page', logger_name)
    response = requests.get(
        url=url, headers=get_headers(api_key), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(VETTY_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_packages(auth_token: str):
    url = f'{VETTY_API_URL}/packages'
    log_request(url, 'get_packages', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(VETTY_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_screening(auth_token: str, applicant_id: str):
    url = f'{VETTY_API_URL}/screenings/{applicant_id}'
    log_request(url, 'get_screening', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer  {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()
