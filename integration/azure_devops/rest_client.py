import logging
import typing

from tenacity import stop_after_attempt, wait_exponential

from integration import requests
from integration.azure_devops.constants import (
    API_VERSION,
    API_VERSION_4_1,
    AZURE_DEVOPS_DBASE_DEV_API,
    AZURE_DEVOPS_SYSTEM,
    AZURE_DEVOPS_VSAEX_API_ULR,
)
from integration.azure_devops.utils import pagination_azure_devops_objects
from integration.constants import REQUESTS_TIMEOUT
from integration.integration_utils.microsoft_utils import (
    MICROSOFT_ATTEMPTS,
    retry_condition,
    token_header,
)
from integration.log_utils import connection_context, log_action, log_request
from integration.response_handler.handler import raise_client_exceptions
from integration.retry import retry
from integration.settings import AZURE_DEVOPS_SECRET_ID, AZURE_DEVOPS_VSSPS_BASE_URL

HEADERS = {
    'content-type': 'application/x-www-form-urlencoded',
}
# USE YOUR NGROK HTTPS URL FOR TESTING PURPOSES
TEST_NGROK_URL = (
    'https://562d-190-204-120-126.ngrok.io/integration/azure_boards/callback'
)

CLIENT_ASSERTION_TYPE = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'

logger_name = __name__
logger = logging.getLogger(logger_name)


def _log_values(is_generator: bool = False):
    return dict(
        vendor_name=AZURE_DEVOPS_SYSTEM,
        logger_name=logger_name,
        is_generator=is_generator,
    )


def generate_create_refresh_token_function(secret_id: str):
    @log_action(**_log_values())
    def create_refresh_token(code: str, redirect_uri: str):
        data = {
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'client_assertion_type': CLIENT_ASSERTION_TYPE,
            'client_assertion': secret_id,
            'assertion': code,
            'redirect_uri': redirect_uri,
        }
        url = f'{AZURE_DEVOPS_VSSPS_BASE_URL}/oauth2/token'
        log_request(url, 'create_refresh_token', logger_name)
        response = requests.post(
            url=url, data=data, headers=HEADERS, timeout=REQUESTS_TIMEOUT
        )
        raise_client_exceptions(response=response)
        return response.json()

    return create_refresh_token


def generate_create_access_token_function(secret_id: str):
    @typing.no_type_check
    @log_action(**_log_values())
    def create_access_token(refresh_token: str) -> tuple[str, str]:
        redirect_uri = ''
        if connection_context.get():
            redirect_uri: str = (
                connection_context.get().connection.integration.metadata.get(
                    'param_redirect_uri'
                )
            )
        data = {
            'grant_type': 'refresh_token',
            'client_assertion_type': CLIENT_ASSERTION_TYPE,
            'client_assertion': secret_id,
            'assertion': refresh_token,
            'redirect_uri': redirect_uri,
        }
        url = f'{AZURE_DEVOPS_VSSPS_BASE_URL}/oauth2/token'
        log_request(url, 'create_access_token', logger_name)
        response = requests.post(
            url=url, data=data, headers=HEADERS, timeout=REQUESTS_TIMEOUT
        )
        raise_client_exceptions(response=response)
        return response.json()['access_token'], response.json()['refresh_token']

    return create_access_token


create_access_token = generate_create_access_token_function(AZURE_DEVOPS_SECRET_ID)
create_refresh_token = generate_create_refresh_token_function(AZURE_DEVOPS_SECRET_ID)


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_account_member_id(access_token: str):
    url = f'{AZURE_DEVOPS_VSSPS_BASE_URL}/_apis/profile/profiles/me?{API_VERSION}'
    log_request(url, 'get_created_account_member_info', logger_name)
    response = requests.get(
        url, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    raise_client_exceptions(response=response)
    return response.json()


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_organizations(access_token: str, member_id: str):
    url = (
        f'{AZURE_DEVOPS_VSSPS_BASE_URL}/_apis/accounts'
        f'?memberId={member_id}&{API_VERSION}'
    )
    log_request(url, 'get_organization', logger_name)
    response = requests.get(
        url, headers=token_header(access_token), timeout=REQUESTS_TIMEOUT
    )
    raise_client_exceptions(response=response)
    return response.json()['value']


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_projects_raw_response(token: str, organization_name: str):
    url = (
        f'{AZURE_DEVOPS_DBASE_DEV_API}/{organization_name}/_apis/projects?{API_VERSION}'
    )
    log_request(url, 'get_projects', logger_name)
    return requests.get(url, headers=token_header(token), timeout=REQUESTS_TIMEOUT)


def get_projects(token: str, organization_name: str):
    response = get_projects_raw_response(token, organization_name)
    raise_client_exceptions(response=response)
    return response.json()['value']


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_repositories(token: str, organization_name: str, project_id: str):
    url = (
        f'{AZURE_DEVOPS_DBASE_DEV_API}/{organization_name}/'
        f'{project_id}/_apis/git/repositories?{API_VERSION}'
    )
    log_request(url, 'get_repositories', logger_name)
    response = requests.get(url, headers=token_header(token), timeout=REQUESTS_TIMEOUT)
    raise_client_exceptions(response=response)
    return response.json()['value']


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_pull_request_by_project(token: str, organization_name: str, project_id: str):
    url = (
        f'{AZURE_DEVOPS_DBASE_DEV_API}/{organization_name}/{project_id}'
        '/_apis/git/pullrequests?searchCriteria.status=all'
    )
    return pagination_azure_devops_objects(
        url=url, token=token, api_version=API_VERSION, path='PULL_REQUEST'
    )


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users(token: str, organization_name: str):
    url = f'{AZURE_DEVOPS_VSAEX_API_ULR}/{organization_name}/_apis/userentitlements?'
    return pagination_azure_devops_objects(
        url=url, token=token, api_version=API_VERSION_4_1, path='USERS'
    )


@retry(
    stop=stop_after_attempt(MICROSOFT_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_users_entitlements(token: str, organization_name: str, user_id: str):
    url = (
        f'{AZURE_DEVOPS_VSAEX_API_ULR}/{organization_name}'
        f'/_apis/userentitlements/{user_id}?{API_VERSION}.3'
    )
    log_request(url, 'get_users_entitlements', logger_name)
    response = requests.get(url, headers=token_header(token), timeout=REQUESTS_TIMEOUT)
    raise_client_exceptions(response=response)
    return response.json()
