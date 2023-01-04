import logging
from collections import namedtuple

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.constants import REQUESTS_TIMEOUT
from integration.encryption_utils import decrypt_value
from integration.exceptions import ConnectionResult
from integration.integration_utils.constants import retry_condition
from integration.log_utils import log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import SHORTCUT_API_URL
from integration.utils import wait_if_rate_time_api

API_VERSION = f'{SHORTCUT_API_URL}/api/v3'

SHORTCUT_ATTEMPTS = 3

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name='Shortcut', logger_name=logger_name, is_generator=is_generator
    )


def _build_headers(api_key):
    return {'Shortcut-Token': decrypt_value(api_key)}


@retry(
    stop=stop_after_attempt(SHORTCUT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_workflows_states(api_key: str):
    url = f'{API_VERSION}/workflows'
    log_request(url, 'get_workflows_states', logger_name)
    response = requests.get(
        url=url, headers=_build_headers(api_key), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)

    return {
        states['id']: states['name']
        for workflows in response.json()
        for states in workflows['states']
    }


def get_all_tickets(
    api_key, selected_time_range, selected_workflows=None, project_id=None
):
    # TODO - remove 'project' related code after al
    #  connections_accounts in prod are using workflows.
    has_next = True
    next_page = None
    while has_next:
        if selected_workflows:
            stories, next_page = get_stories(api_key, selected_time_range, next_page)
            for story in stories:
                if str(story.get('workflow_id')) in selected_workflows:
                    yield story
        if project_id:
            stories, next_page = get_stories_by_project_id(
                api_key, project_id, selected_time_range, next_page
            )
            for story in stories:
                yield story

        has_next = next_page


def _get_stories_by_workflow(
    api_key: str, selected_time_range, next_page, selected_workflows
):
    stories, next_page = get_stories(api_key, selected_time_range, next_page)
    for story in stories:
        if str(story.get('workflow_id')) in selected_workflows:
            yield story


def _get_stories_by_project(api_key, selected_time_range, next_page, project_id):
    stories, next_page = get_stories_by_project_id(
        api_key, project_id, selected_time_range, next_page
    )
    for story in stories:
        yield story


@retry(
    stop=stop_after_attempt(SHORTCUT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_stories_by_project_id(
    api_key, project_id, selected_time_range, next_page=None, **kwargs
):
    try:
        url = f'{API_VERSION}/search/stories'
        data = {
            'query': f'project:{project_id} created:{selected_time_range}..*',
            'page_size': '25',
        }
        if next_page:
            url = f'{SHORTCUT_API_URL + next_page}'
            data = None

        log_request(
            url, f'get_stories_by_project_id: {project_id}', logger_name, **kwargs
        )
        response = requests.get(
            url, headers=_build_headers(api_key), data=data, timeout=REQUESTS_TIMEOUT
        )
        wait_if_rate_time_api(response)
        raise_client_exceptions(response=response, **kwargs)
        stories = response.json()
        return stories['data'], stories['next']
    except ConnectionResult as connection_result:
        error = connection_result.error_response.get('error')
        if error and error == 'maximum-results-exceeded':
            logger.info(
                'Error getting stories by project id '
                f'{project_id}. Error: '
                f'{connection_result.error_response}'
            )
            return [], None
        raise connection_result


@retry(
    stop=stop_after_attempt(SHORTCUT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_stories(api_key, selected_time_range, next_page=None):
    try:
        url = f'{API_VERSION}/search/stories'
        data = {
            'query': f'is:story created:{selected_time_range}..*',
            'page_size': '25',
        }
        if next_page:
            url = f'{SHORTCUT_API_URL + next_page}'
            data = None

        log_request(url, 'get_stories', logger_name)
        response = requests.get(
            url, headers=_build_headers(api_key), data=data, timeout=REQUESTS_TIMEOUT
        )
        wait_if_rate_time_api(response)
        raise_client_exceptions(response=response)
        stories = response.json()
        return stories['data'], stories['next']
    except ConnectionResult as connection_result:
        error = connection_result.error_response.get('error')
        if error and error == 'maximum-results-exceeded':
            logger.info(
                f'Error getting stories Error: {connection_result.error_response}'
            )
            return [], None
        raise connection_result


@retry(
    stop=stop_after_attempt(SHORTCUT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_projects(api_key: str):
    url = f'{API_VERSION}/projects'
    log_request(url, 'get_projects', logger_name)
    response = requests.get(
        url=url, headers=_build_headers(api_key), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return {project['id']: project['name'] for project in response.json()}


@retry(
    stop=stop_after_attempt(SHORTCUT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_workflows(api_key: str):
    url = f'{API_VERSION}/workflows'
    log_request(url, 'get_workflows', logger_name)
    response = requests.get(
        url=url, headers=_build_headers(api_key), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return {workflow.get('id'): workflow.get('name') for workflow in response.json()}


@retry(
    stop=stop_after_attempt(SHORTCUT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_members(api_key: str):
    url = f'{API_VERSION}/members'
    log_request(url, 'get_members', logger_name)
    response = requests.get(
        url=url, headers=_build_headers(api_key), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(SHORTCUT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_epics(api_key: str):
    url = f'{API_VERSION}/epics'
    log_request(url, 'get_epics', logger_name)
    response = requests.get(
        url=url, headers=_build_headers(api_key), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return {epic['id']: epic['name'] for epic in response.json()}


@retry(
    stop=stop_after_attempt(SHORTCUT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_history_details(api_key: str, story_id: str):
    url = f'{API_VERSION}/stories/{story_id}/history'
    log_request(url, 'get_history_details', logger_name)
    response = requests.get(
        url=url, headers=_build_headers(api_key), timeout=REQUESTS_TIMEOUT
    )
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return response.json()


def list_change_requests(
    api_key, selected_time_range, selected_workflows=None, projects_filter=None
):
    if projects_filter:
        for project_id in projects_filter:
            tickets = get_all_tickets(
                api_key, selected_time_range, project_id=project_id
            )
            for ticket in tickets:
                histories = get_history_details(api_key, ticket.get('id'))
                yield RawChangeRequest(data=ticket, histories=histories)
    if selected_workflows:
        tickets = get_all_tickets(
            api_key, selected_time_range, selected_workflows=selected_workflows
        )
        for ticket in tickets:
            histories = get_history_details(api_key, ticket.get('id'))
            yield RawChangeRequest(data=ticket, histories=histories)


RawChangeRequest = namedtuple('RawChangeRequest', ('data', 'histories'))
