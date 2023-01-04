import logging
import typing

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.azure_boards.constants import AZURE_BOARDS_SYSTEM
from integration.azure_devops.constants import API_VERSION, AZURE_DEVOPS_DBASE_DEV_API
from integration.azure_devops.rest_client import (
    generate_create_access_token_function,
    generate_create_refresh_token_function,
)
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.microsoft_utils import (
    MICROSOFT_ATTEMPTS,
    retry_condition,
    token_header,
)
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import AZURE_BOARDS_SECRET_ID

HEADERS = {
    'content-type': 'application/x-www-form-urlencoded',
}
# USE YOUR NGROK HTTPS URL FOR TESTING PURPOSES
TEST_NGROK_URL = (
    'https://3081-186-90-207-166.ngrok.io/integration/azure_boards/callback'
)

CLIENT_ASSERTION_TYPE = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name=AZURE_BOARDS_SYSTEM,
        logger_name=logger_name,
        is_generator=is_generator,
    )


create_refresh_token = generate_create_refresh_token_function(AZURE_BOARDS_SECRET_ID)
create_access_token = generate_create_access_token_function(AZURE_BOARDS_SECRET_ID)


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_query_by_id(access_token: str, organization: str, project: str, query_id: str):
    url = (
        f'{AZURE_DEVOPS_DBASE_DEV_API}/{organization}/{project}'
        f'/_apis/wit/queries/{query_id}?$depth=2&{API_VERSION}'
    )
    log_request(url, 'get_query_by_id', logger_name)
    response = requests.get(
        url, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    return response


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_work_item_query(
    access_token: str,
    organization: str,
    project: str,
    folder: str,
    name: str,
    query: str,
):
    url = (
        f'{AZURE_DEVOPS_DBASE_DEV_API}/{organization}/{project}'
        f'/_apis/wit/queries/{folder}?{API_VERSION}'
    )
    log_request(url, 'create_work_item_query', logger_name)
    response = requests.post(
        url,
        headers=token_header(access_token),
        json={
            'name': name,
            'wiql': query,
        },
        timeout=REQUESTS_TIMEOUT,
    )
    raise_client_exceptions(response=response)
    return response


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_wiql_from_query(access_token: str, query: typing.Any):
    wiql_href = query.json()['_links']['wiql']['href']
    log_request(wiql_href, 'get_wiql_from_query', logger_name)
    response = requests.get(
        wiql_href, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    raise_client_exceptions(response=response)
    return response


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_work_items_by_ids(
    access_token: str, organization: str, project: str, ids: list
):
    url = (
        f'{AZURE_DEVOPS_DBASE_DEV_API}/{organization}/{project}'
        f'/_apis/wit/workItems?$expand=all&ids={",".join(ids)}&{API_VERSION}'
    )
    log_request(url, 'get_work_items_by_ids', logger_name)
    response = requests.get(
        url, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    raise_client_exceptions(response=response)
    return response


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_work_item_updates(access_token: str, work_item: typing.Any):
    url = work_item.get('_links', {}).get('workItemUpdates', {}).get('href', '')
    log_request(url, 'get_work_item_updates', logger_name)
    response = requests.get(url, headers=token_header(access_token))
    raise_client_exceptions(response=response)
    return response
