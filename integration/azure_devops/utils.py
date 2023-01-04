import logging
from typing import Union

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.microsoft_utils import (
    MICROSOFT_ATTEMPTS,
    retry_condition,
    token_header,
)
from integration.log_utils import log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.token import TokenProvider

pager = 100

logger_name = __name__
logger = logging.getLogger(logger_name)


def pagination_azure_devops_objects(
    url: str, token: Union[str, TokenProvider], api_version: str, path: str = ''
):
    skip = 0
    while True:
        # Retrieve next Data based on pager value, or all remaining if less than value
        request_url = _build_pagination_url(skip, url, path, api_version)

        @retry(
            stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
            wait=wait_exponential(),
            reraise=True,
            retry=retry_condition,
        )
        def _get_objects():
            access_token = token if isinstance(token, str) else token()
            log_request(
                request_url,
                f'azure_devops_pagination-version: {api_version}',
                logger_name,
            )
            response = requests.get(
                request_url,
                headers=token_header(access_token),
                timeout=REQUESTS_TIMEOUT,
            )
            raise_client_exceptions(response=response)
            return response

        # If no data returned, break out of loop, otherwise yield new data
        json_response = _get_objects().json()
        if len(json_response['value']) == 0:
            break
        else:
            yield from json_response['value']
            skip += pager


def _build_pagination_url(skip: int, url: str, path: str, api_version: str):
    filters = {
        'USERS': f'{url}top={pager}&skip={skip}&{api_version}',
        'PULL_REQUEST': f'{url}&$top={pager}&$skip={skip}&{api_version}',
    }
    return filters.get(path, '')
