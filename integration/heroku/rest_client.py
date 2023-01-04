import logging
import time

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import HEROKU_API_URL

ACCEPT_HEADER = 'application/vnd.heroku+json; version=3'
HEROKU_ATTEMPTS = '3'
PAGE_SIZE = 1

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False) -> dict:
    return dict(
        vendor_name='Heroku', logger_name=logger_name, is_generator=is_generator
    )


def _build_headers(api_key: str) -> dict[str, str]:
    return dict(
        Authorization=f'Bearer {api_key}',
        Accept=ACCEPT_HEADER,
    )


@retry(
    stop=stop_after_attempt(HEROKU_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_teams(api_key: str) -> list[dict[str, str]]:
    url: str = f'{HEROKU_API_URL}/teams'
    log_request(url, 'get_teams', logger_name)
    response = requests.get(url=url, headers=_build_headers(api_key))
    wait_if_rate_limit(response.headers, url)
    raise_client_exceptions(response=response)
    return response.json()


@log_action(**_log_values())
def get_team_members(api_key: str, team_id: str) -> list[dict[str, str]]:
    return paginator(api_key, f'/teams/{team_id}/members')


@log_action(**_log_values())
def paginator(api_key: str, request_segment: str = ''):
    headers: dict[str, str] = {}
    responses = []

    @retry(
        stop=stop_after_attempt(HEROKU_ATTEMPTS),
        wait=wait_exponential(),
        reraise=True,
        retry=retry_condition,
    )
    def get_data() -> requests.Response:
        url: str = f'{HEROKU_API_URL}{request_segment}'
        log_request(url, 'Heroku paginator', logger_name)
        res = requests.get(
            url,
            headers=dict(**_build_headers(api_key), Range=f'id; max={PAGE_SIZE}')
            if headers == {}
            else headers,
        )
        wait_if_rate_limit(res.headers, url)
        raise_client_exceptions(response=res)
        return res

    data = get_data()
    next_range = data.headers.get('Next-Range')
    responses += data.json()
    _update_range_header(api_key, headers, next_range)
    while next_range:
        response = get_data()
        responses += response.json()
        next_range = response.headers.get('Next-Range')
        _update_range_header(api_key, headers, next_range)

    return responses


def wait_if_rate_limit(headers, url: str):
    rate_remaining = headers.get('Ratelimit-Remaining')
    if rate_remaining and int(rate_remaining) == 0:
        message = (
            'message: Limit reached, waiting 1 minute to continue with the endpoint:'
            f' {url}'
        )
        logger.info(msg=message)
        time.sleep(60)


def _update_range_header(api_key: str, headers: dict, next_range: str):
    headers.update(**_build_headers(api_key), Range=next_range)
