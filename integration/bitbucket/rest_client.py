import logging

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import (
    BITBUCKET_API_ENDPOINT,
    BITBUCKET_CLIENT_ID,
    BITBUCKET_CLIENT_SECRET,
    BITBUCKET_OAUTH_ENDPOINT,
)
from integration.utils import wait_if_rate_time_api

API_URL = 'https://api.bitbucket.org/2.0'

logger_name = __name__
logger = logging.getLogger(logger_name)

BITBUCKET_ATTEMPTS = 3


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Bitbucket', logger_name=logger_name, is_generator=is_generator
    )


def _get_header(access_token):
    return {'Authorization': f'Bearer {access_token}'}


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_access_token(code: str, **kwargs):
    url = f'{BITBUCKET_OAUTH_ENDPOINT}/access_token'
    log_request(url, 'get_access_token', logger_name, **kwargs)
    response = requests.post(
        url=url,
        data={'grant_type': 'authorization_code', 'code': code},
        auth=(BITBUCKET_CLIENT_ID, BITBUCKET_CLIENT_SECRET),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_refresh_token(refresh_token: str, **kwargs):
    url = f'{BITBUCKET_OAUTH_ENDPOINT}/access_token'
    log_request(url, 'get_refresh_token', logger_name, **kwargs)
    response = requests.post(
        url=url,
        data={'grant_type': 'refresh_token', 'refresh_token': refresh_token},
        auth=(BITBUCKET_CLIENT_ID, BITBUCKET_CLIENT_SECRET),
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _get_workspaces(access_token: str, **kwargs):
    url = f'{BITBUCKET_API_ENDPOINT}/2.0/workspaces'
    log_request(url, '_get_workspaces', logger_name, **kwargs)
    response = requests.get(
        url=url, headers=_get_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)

    return response.json()['values']


def _apply_query_to_url(query_function, url, *args):
    has_next = False
    if url is None:
        return has_next, None
    return not has_next, query_function(url, *args)


def _get_url_with_privacy_filter_query(url: str, visibility: str) -> str:
    if not visibility or len(visibility) >= 2:
        return url
    is_private = str(visibility[0] == 'PRIVATE').lower()
    visibility_query_parameter_in_url = 'q=is_private' in url

    return (
        f'{url}?q=is_private={is_private}'
        if not visibility_query_parameter_in_url
        else url
    )


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _get_workspace_repositories(access_token: str, url: str, **kwargs):
    log_request(url, '_get_workspace_repositories', logger_name, **kwargs)
    response = requests.get(
        url, headers=_get_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)

    json_response = response.json()
    return json_response.get('values', []), json_response.get('next')


def _get_all_workspace_repositories(
    access_token: str, workspace_slug: str, visibility: str, **kwargs
):
    has_next, url = _apply_query_to_url(
        _get_url_with_privacy_filter_query,
        f'{API_URL}/repositories/{workspace_slug}',
        visibility,
    )
    while has_next:
        data, next_url = _get_workspace_repositories(access_token, url, **kwargs)
        for repository in data:
            yield repository
        has_next, url = _apply_query_to_url(
            _get_url_with_privacy_filter_query, next_url, visibility
        )


def _apply_query_to_pull_request_url(url, selected_time_range):
    if '&page=' in url:
        return url
    return (
        f'{url}?q=(state="MERGED" OR state="OPEN" OR state="DECLINED") '
        f'AND created_on >= {selected_time_range}'
    )


def _get_all_repository_pull_requests(
    access_token: str, repository: dict, selected_time_range: str, **kwargs
):
    url = repository['links']['pullrequests']['href']
    has_next, url = _apply_query_to_url(
        _apply_query_to_pull_request_url, url, selected_time_range
    )
    while has_next:
        data, next_url = _get_repository_pull_requests(access_token, url, **kwargs)
        for pr in data:
            yield pr
        has_next, url = _apply_query_to_url(
            _apply_query_to_pull_request_url, next_url, selected_time_range
        )


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _get_repository_pull_requests(access_token: str, url: str, **kwargs):
    log_request(url, '_get_repository_pull_requests', logger_name, **kwargs)
    response = requests.get(
        url=url, headers=_get_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    json_response = response.json()
    return json_response.get('values', []), json_response.get('next')


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _get_pull_request_activities(access_token, activities_href, **kwargs):
    log_request(activities_href, '_get_pull_request_activities', logger_name, **kwargs)
    response = requests.get(
        activities_href, headers=_get_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()['values']


def _get_approval_from_activities(access_token: str, activities: dict, **kwargs):
    approvals = []
    for individual_activity in _get_pull_request_activities(
        access_token, activities['links']['activity']['href'], **kwargs
    ):
        if 'approval' in individual_activity:
            approvals.append(individual_activity['approval']['user']['display_name'])
    return list(set(approvals))


def get_pull_requests(
    access_token: str,
    workspaces: list,
    visibility: str,
    selected_time_range: str,
    **kwargs,
):
    for workspace_slug in workspaces:
        for repository in _get_all_workspace_repositories(
            access_token, workspace_slug, visibility, **kwargs
        ):
            pr_visibility = 'Private' if repository['is_private'] else 'Public'
            for pull_request in _get_all_repository_pull_requests(
                access_token, repository, selected_time_range, **kwargs
            ):
                approvals = _get_approval_from_activities(
                    access_token, pull_request, **kwargs
                )
                yield {
                    'repository': repository,
                    'pull_request': pull_request,
                    'approvals': approvals,
                    'pr_visibility': pr_visibility,
                }


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _get_workspace_members(access_token: str, workspace_slug: str, **kwargs):
    url = f'{API_URL}/workspaces/{workspace_slug}/members'
    log_request(url, '_get_workspace_members', logger_name, **kwargs)
    response = requests.get(
        url=url, headers=_get_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json().get('values', [])


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _get_member_details(access_token: str, member: dict, **kwargs):
    url = member['links']['self']['href']
    log_request(url, '_get_member_details', logger_name, **kwargs)
    response = requests.get(
        url=url, headers=_get_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()


@retry(
    stop=stop_after_attempt(BITBUCKET_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def _get_user(access_token: str, member: dict, **kwargs):
    member_details = _get_member_details(access_token, member, **kwargs)
    user_href = member_details["user"]["links"]["self"]["href"]
    url = f'{user_href}?fields=%2Bhas_2fa_enabled'
    log_request(url, '_get_user', logger_name, **kwargs)
    response = requests.get(
        url=url, headers=_get_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, **kwargs)
    return response.json()


def get_users(access_token: str, workspaces: list, **kwargs):
    for workspace_slug in workspaces:
        for member in _get_workspace_members(access_token, workspace_slug, **kwargs):
            user = _get_user(access_token, member, **kwargs)
            yield {'workspace': member['workspace'], 'user': user}


def get_repositories(access_token: str, workspaces: list, visibility: str, **kwargs):
    for workspace_slug in workspaces:
        for repository in _get_all_workspace_repositories(
            access_token, workspace_slug, visibility, **kwargs
        ):
            yield repository


def get_all_workspaces(access_token: str, **kwargs):
    return _get_workspaces(access_token, **kwargs)
