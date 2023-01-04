import logging
import typing

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.digitalocean.constants import (
    DIGITALOCEAN,
    DIGITALOCEAN_ATTEMPTS,
    ITEMS_PER_PAGE,
)
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import DIGITALOCEAN_API_URL

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name=DIGITALOCEAN, logger_name=logger_name, is_generator=is_generator
    )


def get_authorization_header(access_token: str) -> dict:
    return {'Authorization': f'Bearer {access_token}'}


def _get_next_page_url(page: typing.Any) -> str:
    return (
        page.get('links', {})
        .get('pages', {})
        .get('next', '')
        .replace('https//', 'https://', 1)
    )


@retry(
    stop=stop_after_attempt(DIGITALOCEAN_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_alert_policies(access_token: str, items_per_page: int) -> requests.Response:
    url = f'{DIGITALOCEAN_API_URL}/monitoring/alerts'
    log_request(url, 'get_alert_policies', logger_name)
    response = requests.get(
        url,
        headers=get_authorization_header(access_token),
        timeout=REQUESTS_TIMEOUT,
        params={'per_page': items_per_page},
    )
    raise_client_exceptions(response=response)
    return response


def get_paginated_alert_policies(access_token: str) -> list:
    page = get_alert_policies(
        access_token=access_token, items_per_page=ITEMS_PER_PAGE
    ).json()
    next_page = _get_next_page_url(page)
    data = page.get('policies', [])
    while next_page:
        page = requests.get(
            next_page, headers=get_authorization_header(access_token)
        ).json()
        data.extend(page.get('policies', []))
        next_page = _get_next_page_url(page)
    return data
