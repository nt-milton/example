import logging
from http import HTTPStatus
from typing import List

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.response_handler.utils import get_paginated_api_response
from integration.retry import retry
from integration.settings import (
    ATLASSIAN_API_URL,
    ATLASSIAN_CLIENT_ID,
    ATLASSIAN_CLIENT_SECRET,
    ATLASSIAN_OAUTH_URL,
)
from integration.utils import wait_if_rate_time_api

JIRA_PROJECTS = 'jira_projects'
DATE_RANGE_FILTER = 'date_range_filter'

NO_CONTENT = 204
APPLICATION_JSON = 'application/json'
JIRA_ATTEMPTS = 3
MAX_RESULTS_PAGINATION = 50

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(vendor_name='Jira', logger_name=logger_name, is_generator=is_generator)


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_refresh_token(code: str, redirect_uri: str):
    data = {
        'grant_type': 'authorization_code',
        'client_secret': ATLASSIAN_CLIENT_SECRET,
        'client_id': ATLASSIAN_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'code': code,
    }
    headers = {'content-type': APPLICATION_JSON}
    url = ATLASSIAN_OAUTH_URL
    log_request(url, 'create_refresh_token', logger_name)
    response = requests.post(
        url=url, json=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def accessible_resources(auth_token: str):
    url = f'{ATLASSIAN_API_URL}/oauth/token/accessible-resources'
    log_request(url, 'accessible_resources', logger_name)
    response = requests.get(
        url=url,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def create_access_token(refresh_token: str):
    data = {
        'grant_type': 'refresh_token',
        'client_secret': ATLASSIAN_CLIENT_SECRET,
        'client_id': ATLASSIAN_CLIENT_ID,
        'refresh_token': refresh_token,
    }
    url = ATLASSIAN_OAUTH_URL
    headers = {'content-type': APPLICATION_JSON}
    log_request(url, 'create_access_token', logger_name)
    response = requests.post(
        url=url, json=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    access_token = response.json().get('access_token')
    rotating_refresh_token = response.json().get('refresh_token', refresh_token)
    return access_token, rotating_refresh_token


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_projects_with_permissions(
    cloud_id: str,
    permissions: list,
    auth_token: str,
):
    url = f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}/rest/api/3/permissions/project'
    data = {'permissions': permissions}
    log_request(url, 'get_projects_with_permissions', logger_name)
    response = requests.post(
        url,
        json=data,
        headers={'Authorization': f'Bearer {auth_token}'},
        timeout=REQUESTS_TIMEOUT,
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def validate_status_project(
    cloud_id: str,
    project_id: str,
    auth_token: str,
) -> bool:
    project_url = f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}'
    project_url += f'/rest/api/3/project/{project_id}'
    headers = {'Authorization': f'Bearer {auth_token}'}
    log_request(project_url, 'validate_status_project', logger_name)
    response = requests.get(project_url, headers=headers, timeout=REQUESTS_TIMEOUT)
    if response.status_code == 404:
        return False
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response, vendor='Jira')
    return True


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
def get_resource_page(url, page, max_results, value, auth_token):
    headers = {'Authorization': f'Bearer {auth_token}'}
    response = requests.get(url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    data = response.json()
    has_error = response.status_code != HTTPStatus.OK or 'total' not in data
    if has_error:
        raise ConnectionError(f'Jira error {response.status_code} {data}')
    has_next_page = data['total'] > (page + 1) * max_results
    return has_next_page, data[value]


def _get_jql_projects(projects):
    if not projects:
        return None

    join = ', '.join([f'"{project}"' for project in projects])
    return f'({join})'


def generate_url(cloud_id: str, page=0, max_results=100, fields: list = None, **kwargs):
    date_range_filter = kwargs.get(DATE_RANGE_FILTER, None)
    projects = kwargs.get(JIRA_PROJECTS, [])
    url = f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}/rest/api/2/search'

    jql_and_queries = []
    if projects:
        jql_projects = f'project in {_get_jql_projects(projects)}'
        jql_and_queries.append(jql_projects)
    jql_date = f'updatedDate >= "{date_range_filter}"'
    jql_and_queries.append(jql_date)
    jql_query = ' AND '.join(jql_and_queries)
    jql_order = ' order by updated DESC'
    jql = f'{jql_query}{jql_order}'

    query_string = []
    if not fields:
        query_string.append(('expand', 'changelog'))
    query_string.append(('maxResults', max_results))
    query_string.append(('startAt', page * max_results))
    query_string.append(('jql', jql))
    if fields:
        query_string.append(('fields', ','.join(fields)))
    formatted_qs = '&'.join([f'{key}={value}' for key, value in query_string])
    url = f'{url}?{formatted_qs}'
    return url


@log_action(**_log_values())
def get_tickets_page(
    cloud_id: str, auth_token: str, page: int = 0, max_results: int = 100, **kwargs
):
    date_range_filter = kwargs.get(DATE_RANGE_FILTER)
    search_url = f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}/rest/api/2/search'
    jql = f'createdDate >= "{date_range_filter}" order by updated DESC'
    if JIRA_PROJECTS in kwargs:
        projects = kwargs.get(JIRA_PROJECTS, [])
        jql_projects = _get_jql_projects(projects)
        jql = f'project in {jql_projects} AND {jql}' if jql_projects else jql

    pagination = f'maxResults={max_results}&startAt={page * max_results}'
    url = f'{search_url}?expand=changelog&jql={jql}&{pagination}'
    log_request(url, 'get_tickets_page', logger_name)
    return get_resource_page(url, page, max_results, 'issues', auth_token)


@log_action(**_log_values())
def get_projects_page(
    cloud_id: str,
    auth_token: str,
    page: int = 0,
    max_results: int = MAX_RESULTS_PAGINATION,
):
    search_url = f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}'
    search_url += '/rest/api/3/project/search'
    pagination = f'maxResults={max_results}&startAt={page * max_results}'
    url = f'{search_url}?{pagination}'
    log_request(url, 'get_projects_page', logger_name)
    return get_resource_page(url, page, max_results, 'values', auth_token)


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_report_account(report_account: str, auth_token: str):
    report_url = f'{ATLASSIAN_API_URL}/app/report-accounts/'
    data = {'accounts': [report_account]}
    headers = {
        'content-type': APPLICATION_JSON,
        'Authorization': f'Bearer {auth_token}',
    }
    log_request(report_url, 'get_report_account', logger_name)
    response = requests.post(
        report_url, json=data, headers=headers, timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    if response.status_code == NO_CONTENT:
        return None
    accounts = response.json().get('accounts', [])
    return accounts[0] if accounts else None


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_groups_data(
    cloud_id: str,
    auth_token: str,
    max_results: int = MAX_RESULTS_PAGINATION,
    start_at: int = 0,
):
    max_results_param = f'maxResults={max_results}'
    start_at_param = f'startAt={start_at}'
    search_url = (
        f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}'
        f'/rest/api/3/group/bulk?{max_results_param}&{start_at_param}'
    )
    headers = {'Authorization': f'Bearer {auth_token}'}
    log_request(search_url, 'get_all_groups', logger_name)
    response = requests.get(search_url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


def get_all_groups(cloud_id: str, auth_token: str):
    def get_groups_paged(current_page, page_size):
        return get_groups_data(
            cloud_id=cloud_id,
            auth_token=auth_token,
            start_at=current_page * page_size,
            max_results=page_size,
        )

    return get_paginated_api_response(
        api_request=get_groups_paged,
        next_iteration_condition=lambda **page_data: not page_data.get(
            'response', {}
        ).get('isLast', False),
        page_size=50,
        objects_to_append=lambda response: response['values'],
    )


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users_by_group(
    group_id: str,
    cloud_id: str,
    auth_token: str,
    max_results: int = MAX_RESULTS_PAGINATION,
    start_at: int = 0,
):
    max_results_param = f'maxResults={max_results}'
    start_at_param = f'startAt={start_at}'
    search_url = (
        f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}'
        f'/rest/api/3/group/member?groupId={group_id}'
        f'&{max_results_param}&{start_at_param}'
    )
    headers = {'Authorization': f'Bearer {auth_token}'}
    log_request(search_url, 'get_users_by_group', logger_name)
    response = requests.get(search_url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@log_action(**_log_values())
def validate_user_permissions(
    cloud_id: str,
    group_id: str,
    auth_token: str,
):
    search_url = (
        f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}'
        f'/rest/api/3/group/member?groupId={group_id}'
    )
    headers = {'Authorization': f'Bearer {auth_token}'}
    log_request(search_url, 'validate_user_permissions', logger_name)
    response = requests.get(search_url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    return response.json()


def get_all_users_by_group(
    group_id: str,
    cloud_id: str,
    auth_token: str,
    page_size: int = MAX_RESULTS_PAGINATION,
) -> List:
    def get_users_group_paged(current_page, current_page_size):
        return get_users_by_group(
            group_id=group_id,
            cloud_id=cloud_id,
            auth_token=auth_token,
            max_results=page_size,
            start_at=current_page * current_page_size,
        )

    return get_paginated_api_response(
        api_request=get_users_group_paged,
        next_iteration_condition=lambda **page_data: not page_data.get(
            'response', {}
        ).get('isLast', False),
        page_size=page_size,
        objects_to_append=lambda response: response['values'],
    )


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users_data(
    cloud_id: str,
    auth_token: str,
    max_results: int = MAX_RESULTS_PAGINATION,
    start_at: int = 0,
):
    max_results_param = f'maxResults={max_results}'
    start_at_param = f'startAt={start_at}'
    search_url = (
        f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}'
        f'/rest/api/3/users?{max_results_param}&{start_at_param}'
    )
    headers = {'Authorization': f'Bearer {auth_token}'}
    log_request(search_url, 'get_users_data', logger_name)
    response = requests.get(search_url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


def get_all_users_data(cloud_id: str, auth_token: str):
    def get_users_paged(current_page: int, page_size: int):
        return get_users_data(
            cloud_id=cloud_id,
            auth_token=auth_token,
            start_at=current_page * page_size,
            max_results=page_size,
        )

    return get_paginated_api_response(
        api_request=get_users_paged,
        next_iteration_condition=lambda **page_data: len(page_data.get('response', []))
        > 0,
        page_size=50,
    )


@retry(
    stop=stop_after_attempt(JIRA_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_fields(cloud_id: str, auth_token: str):
    search_url = f'{ATLASSIAN_API_URL}/ex/jira/{cloud_id}/rest/api/3/field'
    headers = {'Authorization': f'Bearer {auth_token}'}
    log_request(search_url, 'get_fields', logger_name)
    response = requests.get(search_url, headers=headers, timeout=REQUESTS_TIMEOUT)
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return response.json()
