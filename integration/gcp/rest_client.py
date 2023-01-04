import json
import logging

from google.auth.transport.urllib3 import AuthorizedHttp
from google.oauth2 import service_account
from tenacity import stop_after_attempt, wait_exponential

from integration.exceptions import ConfigurationError
from integration.integration_utils.constants import retry_condition
from integration.integration_utils.custom_errors import get_gcp_custom_error
from integration.response_handler.handler import raise_client_exceptions
from integration.utils import wait_if_rate_time_api

from ..log_utils import log_action, log_request
from ..retry import retry
from .utils import (
    CLOUD_PLATFORM_SCOPE,
    PROJECTS_URL,
    REQUIRED_SERVICES,
    SERVICE_ACCOUNT_PERMISSIONS,
    SERVICE_ACCOUNT_URL,
)

POST = 'POST'
GET = 'GET'
NOT_PROJECT_ACCESS = 'The caller does not have permission'
ERROR = 'error'
GCP_ERRORS = ['PERMISSION_DENIED', 'INVALID_ARGUMENT', 'NOT_FOUND']
PAGE_SIZE = 50

logger_name = __name__
logger = logging.getLogger(logger_name)

GCP_ATTEMPTS = 3


def _log_values(is_generator: bool = False):
    return dict(vendor_name='GCP', logger_name=logger_name, is_generator=is_generator)


def _get_json_data(response):
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return json.loads(response.data.decode('utf-8'))


def _get_json(response):
    return json.loads(response.accounts.decode('utf-8'))


@log_action(**_log_values())
def get_credentials(json_credentials):
    try:
        log_request('Credentials', 'get_credentials', logger_name)
        return service_account.Credentials.from_service_account_info(json_credentials)
    except ValueError as error:
        logger.error(f'Error to authenticate with credentials file. Error: {error}')
        error = get_gcp_custom_error(error.args[0])
        raise ConfigurationError.bad_client_credentials(error)


def get_credentials_with_scopes(credentials, scopes=None):
    if scopes is None:
        scopes = [CLOUD_PLATFORM_SCOPE]
    return credentials.with_scopes(scopes)


@retry(
    stop=stop_after_attempt(GCP_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_project_info(scoped_credentials, project_id):
    authed_http = AuthorizedHttp(scoped_credentials)
    url = f'{PROJECTS_URL}/{project_id}'
    log_request(url, 'get_project_info', logger_name)
    response = authed_http.request(GET, url)

    json_response = json.loads(response.data.decode('utf-8'))
    has_project_access = True
    if (
        ERROR in json_response
        and json_response.get('error').get('message') == NOT_PROJECT_ACCESS
    ):
        has_project_access = False
        return json_response, has_project_access

    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return json_response, has_project_access


@retry(
    stop=stop_after_attempt(GCP_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_members_from_project(scoped_credentials, project_id):
    authed_http = AuthorizedHttp(scoped_credentials)
    url = f'{PROJECTS_URL}/{project_id}:getIamPolicy'
    log_request(url, 'get_members_from_project', logger_name)
    return _get_json_data(response=authed_http.request(POST, url))


@retry(
    stop=stop_after_attempt(GCP_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_role_permissions(scoped_credentials, role_id: str):
    authed_http = AuthorizedHttp(scoped_credentials)
    url = f'{SERVICE_ACCOUNT_URL}/{role_id}'
    log_request(url, 'get_role_permissions', logger_name)
    response = authed_http.request(GET, url)
    json_response = json.loads(response.data.decode('utf-8'))
    if ERROR in json_response:
        response_status: str = json_response.get('error', {}).get('status')
        error_message: str = json_response.get('error', {}).get('message')
        if response_status in GCP_ERRORS:
            logger.info(
                f'Error getting role permissions due GCP error {response_status} and'
                f'caused by: {error_message}'
            )
            return []
    wait_if_rate_time_api(response)
    raise_client_exceptions(response=response)
    return json_response.get('includedPermissions', [])


@retry(
    stop=stop_after_attempt(GCP_ATTEMPTS),
    wait=wait_exponential(),
    reraise=True,
    retry=retry_condition,
)
@log_action(**_log_values())
def get_service_accounts_from_project(
    scoped_credentials,
    project_id,
):
    authed_http = AuthorizedHttp(scoped_credentials)
    url = f'{SERVICE_ACCOUNT_URL}/projects/{project_id}/serviceAccounts'
    log_request(url, 'get_service_accounts_from_project', logger_name)
    return _get_json_data(response=authed_http.request(GET, url))


def get_batch_services_info(
    scoped_credentials: str,
    project: str,
):
    url = (
        'https://serviceusage.googleapis.com/v1/projects/'
        f'{project}/services?pageSize={PAGE_SIZE}'
    )
    all_services = []
    response = _google_page_generator(scoped_credentials, 'services', url)
    for service in response:
        if service['config']['name'] in REQUIRED_SERVICES:
            service_object = {
                'title': service['config']['title'],
                'state': service['state'],
                'name': service['config']['name'],
            }
            all_services.append(service_object)
    return all_services


@log_action(**_log_values())
def _google_page_generator(credentials, response_key, url=None):
    @retry(
        stop=stop_after_attempt(GCP_ATTEMPTS),
        wait=wait_exponential(),
        reraise=True,
        retry=retry_condition,
    )
    def _request_page(current_url):
        log_request(current_url, 'google_service', logger_name)
        return _get_json_data(
            response=authed_http.request(GET, current_url),
        )

    authed_http = AuthorizedHttp(credentials)
    default_url = url
    while url:
        response = _request_page(url)

        yield from response.get(response_key)
        if response.get('nextPageToken'):
            next_token = response.get('nextPageToken')
            url = f'{default_url}&pageToken={next_token}'
        else:
            url = None


def check_iam_permissions(scoped_credentials, project_id):
    authed_http = AuthorizedHttp(scoped_credentials)
    url = f'{PROJECTS_URL}/{project_id}:testIamPermissions'
    body = {'permissions': SERVICE_ACCOUNT_PERMISSIONS}
    log_request(url, 'check_iam_permissions', logger_name)
    response = _get_json_data(
        response=authed_http.request(POST, url, body=json.dumps(body)),
    )

    def _have_required_permissions(current_response):
        current_response = current_response.get('permissions')
        return (
            current_response
            and len(current_response) == 2
            and SERVICE_ACCOUNT_PERMISSIONS[0] in current_response
            and SERVICE_ACCOUNT_PERMISSIONS[1] in current_response
        )

    if type(response) != dict or not _have_required_permissions(response):
        response = {
            'message': (
                'The service account does not have the minimum '
                f'permissions of {SERVICE_ACCOUNT_PERMISSIONS} that '
                'the viewer role must have, check the viewer '
                'role assignment'
            )
        }
        raise ConfigurationError.insufficient_permission(response=response)
