import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Union

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.datadog.mapper import DatadogData
from integration.encryption_utils import decrypt_value
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request, logger_extra
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry

ONE_MONTH_TIMEFRAME = 2764800
MAX_EMPTY_MONTHS = 12
API_LIMIT = 1
PAGE_SIZE = 50

logger_name = __name__
logger = logging.getLogger(logger_name)

DATADOG_ATTEMPTS = 3


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Datadog', logger_name=logger_name, is_generator=is_generator
    )


def _get_headers_object(api_key: str, application_key: str) -> Dict:
    return {
        'DD-API-KEY': decrypt_value(api_key),
        'DD-APPLICATION-KEY': decrypt_value(application_key),
    }


@retry(
    stop=stop_after_attempt(DATADOG_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def list_monitors(
    site: str, api_key: str, application_key: str, raise_exception: bool = False
):
    url = f'{site}/v1/monitor'
    log_request(url, 'list_monitors', logger_name)
    response = requests.get(
        url,
        headers=_get_headers_object(api_key, application_key),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_api_limit(response=response)
    result = raise_client_exceptions(
        response=response,
        raise_exception=raise_exception,
    )
    if result.with_error():
        message = 'Error getting monitors'
        if result.status_code == '403':
            message += f' - Not access to the service on site {site}'
        logger.info(logger_extra(message=message))

    return response.json()


@log_action(**_log_values())
def pull_events(
    site: str,
    api_key: str,
    application_key: str,
    store_events: Callable,
    chunk_size: int,
    gap_size: int = MAX_EMPTY_MONTHS,
    start: Union[float, None] = None,
):
    end = int(time.time())
    current_gap_size = 0
    pulled_events: List[Any] = []
    # This condition evaluates a max of 12 months of empty records
    while current_gap_size <= gap_size:
        if start and start > end:
            break

        if len(pulled_events) > chunk_size:
            store_events(pulled_events)
            pulled_events.clear()

        current_page_events = _request_events(
            site,
            api_key,
            application_key,
            start=start,
            end=end,
        )
        end -= ONE_MONTH_TIMEFRAME + 1
        current_gap_size = 0 if len(current_page_events) else current_gap_size + 1
        pulled_events.extend(current_page_events)

    if len(pulled_events) > 0:
        store_events(pulled_events)


@retry(
    stop=stop_after_attempt(DATADOG_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _request_events(
    site: str,
    api_key: str,
    application_key: str,
    start=None,
    end=None,
):
    if end is None:
        end = int(time.time())
    max_start = end - ONE_MONTH_TIMEFRAME
    if start is None:
        start = max_start
    if max_start > start:
        start = max_start
    start = int(start)
    next_page = f'{site}/v1/events?start={start}&end={end}'
    log_request(next_page, '_request_events', logger_name)
    response = requests.get(
        next_page,
        headers=_get_headers_object(api_key, application_key),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_api_limit(response=response)
    raise_client_exceptions(response=response)
    return response.json()['events']


def _iterate_datadog_page(
    call: Callable, site: str, api_key: str, application_key: str, **kwargs
):
    page_number = 0
    processed_records = 0
    while True:
        records_data = call(
            site=site,
            api_key=api_key,
            application_key=application_key,
            page_number=page_number,
            **kwargs,
        )
        if not records_data:
            return None

        data = records_data.get('data', [])
        meta_page = records_data.get('meta', {}).get('page')
        processed_records += len(data)

        yield DatadogData(data=data, included=records_data.get('included', []))
        if processed_records == meta_page.get('total_count'):
            break

        page_number += 1


def read_all_datadog_users(
    site: str,
    api_key: str,
    application_key: str,
    filter_service_account: bool = False,
):
    datadog_page_values = _iterate_datadog_page(
        call=list_users,
        site=site,
        api_key=api_key,
        application_key=application_key,
        filter_service_account=filter_service_account,
    )
    datadog_page_values = datadog_page_values or []
    for datadog_page in datadog_page_values:
        yield datadog_page


@retry(
    stop=stop_after_attempt(DATADOG_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def list_users(
    site: str,
    api_key: str,
    application_key: str,
    page_number: int = 0,
    filter_service_account: bool = False,
):
    url = (
        f'{site}/v2/users'
        f'?page[size]={PAGE_SIZE}'
        f'&page[number]={page_number}'
        f'&filter[service_account]={str(filter_service_account).lower()}'
    )

    log_request(url, 'list_users', logger_name)
    response = requests.get(
        url,
        headers=_get_headers_object(api_key, application_key),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_api_limit(response=response)
    result = raise_client_exceptions(
        response=response,
        raise_exception=False,
    )
    if result.with_error():
        message = 'Error getting users'
        if result.status_code == '403':
            message += f' - Not access to the service on site {site}'
        logger.warning(logger_extra(message=message))
        return None

    return response.json()


@retry(
    stop=stop_after_attempt(DATADOG_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_managed_organizations(
    site: str,
    api_key: str,
    application_key: str,
):
    url = f'{site}/v1/org'
    log_request(url, 'get_managed_organizations', logger_name)
    response = requests.get(
        url,
        headers=_get_headers_object(api_key, application_key),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_api_limit(response=response)
    result = raise_client_exceptions(
        response=response,
        raise_exception=False,
    )
    if result.with_error():
        message = 'Error getting managed organizations'
        if result.status_code == '403':
            message += f' - Not access to the service on site {site}'
        logger.warning(logger_extra(message=message))
        return None

    return response.json()


def wait_if_api_limit(response: requests.Response) -> None:
    headers = response.headers
    requests_remaining = int(headers.get('X-RateLimit-Remaining', 1))
    reset_timestamp = int(headers.get('X-RateLimit-Reset', 0)) + 15
    if requests_remaining == API_LIMIT:
        current_timestamp = int(datetime.now().timestamp())
        wait_time = reset_timestamp - current_timestamp
        if wait_time >= 0:
            time.sleep(wait_time)
