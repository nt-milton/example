import logging
import time
from base64 import b64encode
from typing import Generator, TypeVar
from urllib.parse import urlencode

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.checkr.checkr_types import Candidate, PaginatedResponse
from integration.checkr.constants import HIERARCHY_ERROR_CODE
from integration.constants import REQUESTS_TIMEOUT
from integration.encryption_utils import decrypt_value
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import CHECKR_API_URL, CHECKR_CLIENT_ID, CHECKR_CLIENT_SECRET
from objects.models import LaikaObject

CHECKR_ATTEMPTS = 3

API_LIMIT = 1

SLEEP_SECONDS = 75

SUCCESS = 200

logger_name = __name__
logger = logging.getLogger(logger_name)

T = TypeVar('T')


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Checkr', logger_name=logger_name, is_generator=is_generator
    )


def get_headers(auth_token):
    encoded_auth = b64encode(f'{decrypt_value(auth_token)}:'.encode()).decode()
    return {'Authorization': f'Basic {encoded_auth}'}


def fetch_auth_token(code: str, **kwargs):
    data = {
        'client_id': CHECKR_CLIENT_ID,
        'client_secret': CHECKR_CLIENT_SECRET,
        'code': code,
    }
    url = f'{CHECKR_API_URL}/oauth/tokens'
    log_request(url, 'fetch_auth_token', logger_name, **kwargs)
    response = requests.post(
        url,
        json=data,
        timeout=REQUESTS_TIMEOUT,
    )
    _handle_rate_limit(response)
    raise_client_exceptions(response)
    return response.json()


def _handle_rate_limit(response):
    limit_remaining = response.headers.get('X-RateLimit-Remaining')
    if limit_remaining and limit_remaining == API_LIMIT:
        logger.info(f'Reached rate limit, waiting {SLEEP_SECONDS} seconds')
        time.sleep(SLEEP_SECONDS)


@retry(
    stop=stop_after_attempt(CHECKR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_account_details(auth_token: str, url: str = '', **kwargs):
    url = f'{CHECKR_API_URL}/v1/{url}'
    log_request(url, 'get_account_details', logger_name, **kwargs)
    response = requests.get(
        url,
        headers=get_headers(auth_token),
    )
    _handle_rate_limit(response)
    raise_client_exceptions(response)
    return response.json()


@retry(
    stop=stop_after_attempt(CHECKR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_nodes(auth_token: str, url: str = '', **kwargs):
    log_request(url, 'get_nodes', logger_name, **kwargs)
    response = requests.get(
        f'{CHECKR_API_URL}/v1/{url}',
        headers=get_headers(auth_token),
        params=kwargs.get('params', {}),
    )

    if response.status_code not in [HIERARCHY_ERROR_CODE, SUCCESS]:
        _handle_rate_limit(response)
        raise_client_exceptions(response)

    return response.json()


@retry(
    stop=stop_after_attempt(CHECKR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_packages(auth_token: str, url: str = '', **kwargs):
    log_request(url, 'get_packages', logger_name, **kwargs)
    response = requests.get(
        f'{CHECKR_API_URL}/v1/{url}',
        headers=get_headers(auth_token),
        params=kwargs.get('params', {}),
    )
    _handle_rate_limit(response)
    raise_client_exceptions(response)
    return response.json()


def create_candidates(auth_token: str, url: str = '', **kwargs):
    url = f'{CHECKR_API_URL}/v1/{url}'
    log_request(url, 'create_candidates', logger_name, **kwargs)
    response = requests.post(
        url, headers=get_headers(auth_token), json=kwargs.get('data')
    )
    raise_client_exceptions(response)
    return response.json()


def send_invitation(auth_token: str, url: str = '', **kwargs):
    url = f'{CHECKR_API_URL}/v1/{url}'
    log_request(url, 'send_invitation', logger_name, **kwargs)
    response = requests.post(
        url, headers=get_headers(auth_token), json=kwargs.get('data')
    )
    _handle_rate_limit(response)
    raise_client_exceptions(response)
    return response.json()


def create_candidate_and_send_invitation(auth_token: str, url='', **kwargs):
    from integration.checkr.implementation import map_background_checks
    from objects.system_types import BACKGROUND_CHECK, resolve_laika_object_type

    _candidate_body = {'data': {'email': kwargs.get('data', {}).pop('email', None)}}
    candidate = create_candidates(auth_token, url, **_candidate_body)
    candidate['user'] = {'email': candidate.pop('email')}
    connection_account = kwargs.pop('connection_account', None)
    if connection_account is None:
        return
    data = map_background_checks(candidate, connection_account.alias)
    kwargs['data']['candidate_id'] = candidate.get('id', None)
    invitation = send_invitation(auth_token, 'invitations', **kwargs)
    data['Status'] = invitation.get('status', '')
    data['Package'] = invitation.get('package', '')
    LaikaObject.objects.create(
        data=data,
        connection_account=connection_account,
        object_type=resolve_laika_object_type(
            connection_account.organization, BACKGROUND_CHECK
        ),
    )

    return invitation


@retry(
    stop=stop_after_attempt(CHECKR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def list_candidates(auth_token: str, **kwargs) -> Generator[Candidate, None, None]:
    next_href = f'{CHECKR_API_URL}/v1/candidates?{urlencode(kwargs)}'
    headers = get_headers(auth_token)
    while next_href:
        log_request(next_href, 'list_candidates', logger_name, **kwargs)
        response = requests.get(next_href, headers=headers).json()
        candidates: list[Candidate] = response.get('data', [])
        next_href = response.get("next_href")
        if next_href:
            next_href += f'&{urlencode(kwargs)}'
        for candidate in candidates:
            yield candidate


@retry(
    stop=stop_after_attempt(CHECKR_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def list_invitations(auth_token: str, **kwargs) -> PaginatedResponse:
    headers = get_headers(auth_token)

    url = f'{CHECKR_API_URL}/v1/invitations/?{urlencode(kwargs)}'
    log_request(url, 'list_invitations', logger_name)
    response = requests.get(url, headers=headers)
    _handle_rate_limit(response)
    raise_client_exceptions(response)
    return response.json()
