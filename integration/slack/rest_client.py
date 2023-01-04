import json
import logging
from typing import Dict, Generator, List, Tuple, Union

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.error_codes import NONE
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request, logger_extra
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import SLACK_API_URL, SLACK_CLIENT_ID, SLACK_CLIENT_SECRET
from integration.utils import wait_if_rate_time_api

APPLICATION_JSON = 'application/json'
APPLICATION_FORM_URL_ENCODED = 'application/x-www-form-urlencoded'
ITEMS_PER_PAGE_LIMIT = 500

# Replace this variable with redirect_uri in function
# fetch_access_token (below) for testing purposes
TEST_NGROK = ('https://3766-181-114-125-71.ngrok.io/integration/slack/callback/',)


SLACK_ATTEMPTS = 3

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(vendor_name='Slack', logger_name=logger_name, is_generator=is_generator)


def _get_headers() -> dict:
    return {'content-type': APPLICATION_FORM_URL_ENCODED}


def _slack_kwargs(**kwargs):
    return {**dict(is_slack_api=True), **kwargs}


@retry(
    stop=stop_after_attempt(SLACK_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def fetch_access_token(code: str, redirect_uri: str, **kwargs) -> dict:
    data = {
        'grant_type': 'authorization_code',
        'client_secret': SLACK_CLIENT_SECRET,
        'client_id': SLACK_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    headers = {'content-type': APPLICATION_FORM_URL_ENCODED}
    url = f'{SLACK_API_URL}/oauth.v2.access'
    log_request(url, 'fetch_access_token', logger_name, **kwargs)
    response = requests.post(
        url=url, data=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response=response)
    result = raise_client_exceptions(response=response, **_slack_kwargs(**kwargs))
    if result.error_code != NONE:
        message = f'Error fetching access token due {result.error_response}'
        logger.info(logger_extra(message, **kwargs))
        raise result

    return response.json()


@retry(
    stop=stop_after_attempt(SLACK_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_slack_channels(
    access_token: str, cursor: str = None, **kwargs
) -> Tuple[List, str]:
    params: Dict[str, Union[int, str]] = {
        'types': 'public_channel,private_channel',
        'limit': ITEMS_PER_PAGE_LIMIT,
        'exclude_archived': 'true',
    }
    if cursor:
        params['cursor'] = cursor

    headers = {
        'content-type': APPLICATION_FORM_URL_ENCODED,
        'Authorization': f'Bearer {access_token}',
    }
    url = f'{SLACK_API_URL}/conversations.list'
    log_request(url, 'get_slack_channels', logger_name, **kwargs)
    response = requests.get(
        url=url, params=params, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response=response)
    result = raise_client_exceptions(response=response, **_slack_kwargs(**kwargs))
    if result.error_code != NONE:
        message = f'Error getting Slack channels due {result.error_response}'
        logger.info(logger_extra(message, **kwargs))
        raise result

    data = response.json()
    channels = data.get('channels', [])
    next_cursor = data.get('response_metadata', {}).get('next_cursor')
    return channels, next_cursor


def get_all_slack_channels(access_token: str, **kwargs) -> Generator[dict, None, None]:
    has_next = True
    cursor = None
    while has_next:
        channels, cursor = get_slack_channels(access_token, cursor, **kwargs)
        for conversation in channels:
            channel = {
                'id': conversation.get('id', ''),
                'name': conversation.get('name', ''),
                'is_private': conversation.get('is_private', False),
                'is_im': conversation.get('is_im', False),
                'is_channel': conversation.get('is_channel', False),
                'is_group': conversation.get('is_group', False),
            }
            yield channel

        if not cursor:
            has_next = False


@retry(
    stop=stop_after_attempt(SLACK_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_slack_users(
    access_token: str, cursor: str = None, **kwargs
) -> Tuple[List, str]:
    params: Dict[str, Union[int, str]] = {
        'limit': ITEMS_PER_PAGE_LIMIT,
        'exclude_archived': 'true',
    }
    if cursor:
        params['cursor'] = cursor
    headers = {
        'content-type': APPLICATION_FORM_URL_ENCODED,
        'Authorization': f'Bearer {access_token}',
    }
    url = f'{SLACK_API_URL}/users.list'
    log_request(url, 'get_slack_users', logger_name, **kwargs)
    response = requests.get(
        url=url, params=params, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response=response)
    result = raise_client_exceptions(
        response=response, raise_exception=False, **_slack_kwargs(**kwargs)
    )
    if result.error_code != NONE:
        message = f'Error getting Slack users due {result.error_response}'
        logger.info(logger_extra(message, **kwargs))
        raise result

    data = response.json()
    members = data.get('members')
    next_cursor = data.get('response_metadata', {}).get('next_cursor')
    return members, next_cursor


def get_all_slack_users(access_token: str, **kwargs) -> Generator[dict, None, None]:
    has_next: bool = True
    cursor = None
    while has_next:
        users, cursor = get_slack_users(access_token, cursor, **kwargs)
        for user in users:
            is_deleted = user.get('deleted', False)
            is_bot = user.get('is_bot', False)

            if is_deleted or is_bot:
                message = 'is deleted' if is_deleted else 'is a bot'
                logger.info(
                    f'Soft deleting user {user.get("name", "")} because {message}'
                )
                continue

            yield user

        if not cursor:
            has_next = False


@retry(
    stop=stop_after_attempt(SLACK_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
def send_slack_message(access_token: str, channel_id: str, blocks: List) -> Dict:
    data = {
        'channel': channel_id,
        'blocks': json.dumps(blocks),
    }
    headers = {
        'content-type': APPLICATION_FORM_URL_ENCODED,
        'Authorization': f'Bearer {access_token}',
    }
    response = requests.post(
        f'{SLACK_API_URL}/chat.postMessage',
        data=data,
        headers=headers,
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response=response)
    result = raise_client_exceptions(
        response=response, raise_exception=False, **dict(is_slack_api=True)
    )
    if result.error_code != NONE:
        message = (
            f'Error sending Slack message to channel id {channel_id} '
            f'due {result.error_response}'
        )
        logger.warning(message)

    return response.json()
