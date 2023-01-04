from pathlib import Path

from urllib3.response import HTTPResponse

SERVICE_ACCOUNT = 'google.oauth2.service_account'
AUTH_HTTP_REQUEST = 'google.auth.transport.urllib3.AuthorizedHttp.request'
CRED_WITH_SCOPES = f'{SERVICE_ACCOUNT}.Credentials.with_scopes'
SERVICE_ACCT_INFO = f'{SERVICE_ACCOUNT}.Credentials.from_service_account_info'

TEST_DIR = Path(__file__).parent

RESOURCE_MANAGER_API = 'https://cloudresourcemanager.googleapis.com/v1/projects'
SERVICE_USAGE_API = 'https://serviceusage.googleapis.com/v1/projects/'
IAM_API = 'https://iam.googleapis.com/v1/projects/'
TEST_IAM_SEGMENT = ':testIamPermissions'
GET_IAM_POLICY = ':getIamPolicy'


def fake_authorized_http_request(http_method, url, body=''):
    if RESOURCE_MANAGER_API in url:
        if GET_IAM_POLICY in url:
            return raw_members_in_projects()
        if TEST_IAM_SEGMENT in url:
            return raw_iam_permissions()
        return raw_projects()
    if SERVICE_USAGE_API in url:
        return raw_services_response()
    if IAM_API in url:
        if 'roles' in url:
            return raw_role_permissions()
        return raw_service_accounts_response()
    return ValueError('Unexpected operation for google cloud fake api')


def fake_authorized_http_request_no_duplicates(http_method, url, body=''):
    if RESOURCE_MANAGER_API in url:
        if GET_IAM_POLICY in url:
            return raw_duplicate_members_in_projects()
        if TEST_IAM_SEGMENT in url:
            return raw_iam_permissions()
        return raw_projects()
    if SERVICE_USAGE_API in url:
        return raw_services_response()
    if IAM_API in url:
        return raw_service_accounts_for_duplicates_response()
    return ValueError('Unexpected operation for google cloud fake api')


def fake_authorized_without_project_access(http_method, url, body=''):
    if RESOURCE_MANAGER_API in url:
        if TEST_IAM_SEGMENT in url:
            return raw_iam_permissions()
        return raw_projects_without_access()


def fake_authorized_resource_manager_error(http_method, url, body=''):
    if RESOURCE_MANAGER_API in url:
        if TEST_IAM_SEGMENT in url:
            return raw_iam_permissions()
        return raw_resource_manager_error()


def fake_authorized_iam_permission_error(http_method, url, body=''):
    if RESOURCE_MANAGER_API in url:
        if TEST_IAM_SEGMENT in url:
            return HTTPResponse(status=200, body=str.encode('{}'))
        return raw_resource_manager_error()


def raw_projects():
    path = TEST_DIR / 'raw_projects.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(status=200, reason='OK', body=str.encode(file_json))


def raw_members_in_projects():
    path = TEST_DIR / 'raw_members_in_projects.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(status=200, reason='OK', body=str.encode(file_json))


def raw_duplicate_members_in_projects():
    path = TEST_DIR / 'raw_duplicate_members_in_project.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(status=200, reason='OK', body=str.encode(file_json))


def raw_services_response():
    path = TEST_DIR / 'raw_google_services_response.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(status=200, reason='OK', body=str.encode(file_json))


def raw_service_accounts_response():
    path = TEST_DIR / 'raw_service_accounts_response.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(status=200, reason='OK', body=str.encode(file_json))


def raw_projects_without_access():
    path = TEST_DIR / 'raw_project_error_response.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(
        status=403, reason='PERMISSION DENIED', body=str.encode(file_json)
    )


def raw_role_permissions():
    path = TEST_DIR / 'raw_iam_roles_permissions_error_response.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(status=404, reason='NOT FOUND', body=str.encode(file_json))


def raw_resource_manager_error():
    path = TEST_DIR / 'raw_resource_manager_error_response.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(
        status=403, reason='PERMISSION DENIED', body=str.encode(file_json)
    )


def raw_iam_permissions():
    path = TEST_DIR / 'raw_iam_test_permissions_response.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(status=200, reason='OK', body=str.encode(file_json))


def raw_service_accounts_for_duplicates_response():
    path = TEST_DIR / 'raw_service_account_for_duplicates.json'
    file_json = open(path, 'r').read()
    return HTTPResponse(status=200, reason='OK', body=str.encode(file_json))
