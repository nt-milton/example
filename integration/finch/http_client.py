import base64
import logging
from collections import Iterable

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.integration_utils.finch_utils import verify_finch_request_id
from integration.log_utils import log_action, log_request, logger_extra
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import FINCH_API_URL, FINCH_CLIENT_ID, FINCH_CLIENT_SECRET
from integration.utils import wait_if_rate_time_api

FINCH_ATTEMPTS = 3

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(vendor_name='Finch', logger_name=logger_name, is_generator=is_generator)


@retry(
    stop=stop_after_attempt(FINCH_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_token(code: str):
    credentials = base64.b64encode(
        f'{FINCH_CLIENT_ID}:{FINCH_CLIENT_SECRET}'.encode()
    ).decode()
    url = f'{FINCH_API_URL}/auth/token'
    log_request(url, 'get_token', logger_name)
    response = requests.post(
        url=url,
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data={'code': code},
        timeout=REQUESTS_TIMEOUT,
    )
    finch_request_id = verify_finch_request_id(response.headers)
    if finch_request_id:
        log_request(
            finch_request_id=finch_request_id,
            logger_name=logger_name,
        )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(FINCH_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def read_directory(token: str):
    url = f'{FINCH_API_URL}/employer/directory'
    log_request(url, 'read_directory', logger_name)
    response = requests.get(
        url=url, headers=finch_headers(token), timeout=REQUESTS_TIMEOUT
    )
    finch_request_id = verify_finch_request_id(response.headers)
    if finch_request_id:
        log_request(
            finch_request_id=finch_request_id,
            logger_name=logger_name,
        )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, check_expiration=True)

    return response.json()


@retry(
    stop=stop_after_attempt(FINCH_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def read_company(token: str):
    url = f'{FINCH_API_URL}/employer/company'
    log_request(url, 'read_company', logger_name)
    response = requests.get(
        url=url, headers=finch_headers(token), timeout=REQUESTS_TIMEOUT
    )
    finch_request_id = verify_finch_request_id(response.headers)
    if finch_request_id:
        log_request(
            finch_request_id=finch_request_id,
            logger_name=logger_name,
        )
    wait_if_rate_time_api(response)
    result = raise_client_exceptions(response=response, raise_exception=False)

    if result.status_code == '501':
        message = 'Company endpoint is not available for API tokens'
        logger.warning(logger_extra(message))
        return None
    elif result.with_error():
        raise result.get_connection_result()
    return response.json()


@retry(
    stop=stop_after_attempt(FINCH_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def read_individual_details(token: str, ids: Iterable[str]):
    request_ids = [{'individual_id': id} for id in ids]
    url = f'{FINCH_API_URL}/employer/individual'
    log_request(url, 'read_individual_details', logger_name)
    response = requests.post(
        url=url,
        headers=finch_headers(token),
        json={'requests': request_ids},
        timeout=REQUESTS_TIMEOUT,
    )
    finch_request_id = verify_finch_request_id(response.headers)
    if finch_request_id:
        log_request(
            finch_request_id=finch_request_id,
            logger_name=logger_name,
        )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(FINCH_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def read_employments(token: str, ids: Iterable[str]):
    request_ids = [{'individual_id': id} for id in ids]
    url = f'{FINCH_API_URL}/employer/employment'
    log_request(url, 'read_employments', logger_name)
    response = requests.post(
        url=url,
        headers=finch_headers(token),
        json={'requests': request_ids},
        timeout=REQUESTS_TIMEOUT,
    )

    finch_request_id = verify_finch_request_id(response.headers)
    if finch_request_id:
        log_request(
            finch_request_id=finch_request_id,
            logger_name=logger_name,
        )
    wait_if_rate_time_api(response)
    # Note: don't log because sensitive data like income
    raise_client_exceptions(response=response, log_unknown_error=False)
    return response.json()


def finch_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'content_type': 'application/json',
        'Finch-API-Version': '2020-09-17',
    }
