from http import HTTPStatus
from pathlib import Path

from httmock import HTTMock, response, urlmatch

TEST_DIR = Path(__file__).parent


def fake_google_workspace_api():
    """This fake will intercept http calls to google domain and
    It will use a fake implementation"""
    return HTTMock(fake_auth, fake_google_api_resources)


def fake_google_tokens_access_api():
    """This fake will intercept http calls to google domain and
    It will use a fake implementation"""
    return HTTMock(fake_auth, fake_org_units, fake_user_api_without_tokens_access)


def fake_google_workspace_api_without_permissions():
    """This fake will intercept http calls to google domain and
    It will use a fake implementation"""
    return HTTMock(fake_auth, fake_not_authorized)


def fake_google_workspace_api_forbidden():
    """This fake will intercept http calls to google domain and
    It will use a fake implementation"""
    return HTTMock(fake_auth, fake_forbidden)


@urlmatch(netloc='www.googleapis.com')
def fake_google_api_resources(url, request):
    if '/admin/directory/v1/customer/my_customer/roles' in url.path:
        return fake_get_roles_list()
    elif '/admin/directory/v1/customer/my_customer/orgunits' in url.path:
        return fake_org_units(url, request)
    elif '/admin/directory/v1/customer/my_customer/roleassignments' in url.path:
        return fake_get_role_assignments()
    if '/admin/directory/v1/users' in url and 'pageToken' in url.query:
        return fake_empty_users_next_page()

    return fake_user_api(url, request)


@urlmatch(netloc='oauth2.googleapis.com')
def fake_auth(url, request):
    access_token_request = 'refresh_token' in request.body
    if access_token_request:
        return '{"access_token":"token"}'
    auth_code_request = 'authorization_code' in request.body
    if auth_code_request:
        return '{"refresh_token":"token" }'
    raise ValueError('Unexpected operation for Google Workspace fake api')


@urlmatch(netloc='www.googleapis.com')
def fake_user_api(url, request):
    user_ids = [
        '103043315594614939856',
        '109287231859442825475',
        '114496349593149367447',
        '115602337442250165067',
    ]
    for user_id in user_ids:
        if user_id in url.path:
            path = TEST_DIR / 'raw_tokens_response.json'
            return open(path, 'r').read()
    return fake_users()


@urlmatch(netloc='www.googleapis.com')
def fake_user_api_without_tokens_access(url, request):
    user_ids = [
        '103043315594614939856',
        '109287231859442825475',
        '114496349593149367447',
        '115602337442250165067',
    ]
    for user_id in user_ids:
        if user_id in url.path:
            if user_id == '115602337442250165067':
                return fake_tokens_not_authorized()
            path = TEST_DIR / 'raw_tokens_response.json'
            return open(path, 'r').read()
    path = TEST_DIR / 'raw_users_response.json'
    return open(path, 'r').read()


@urlmatch(
    netloc='www.googleapis.com',
    path='/admin/directory/v1/customer/my_customer/orgunits',
)
def fake_org_units(url, request):
    path = TEST_DIR / 'raw_org_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='www.googleapis.com')
def fake_not_authorized(url, request):
    return response(
        status_code=HTTPStatus.UNAUTHORIZED,
        content='{"error": {"code":401, "message": "Not Authorized"}}',
    )


@urlmatch(netloc='www.googleapis.com')
def fake_forbidden(url, request):
    return response(
        status_code='403',
        content='{"error": {"code":"403", "message": "Admin API not enabled"}}',
    )


def fake_tokens_not_authorized():
    content = '''
        {
          "error": {
            "code": 401,
            "message": "User does not have credential",
            "errors": [
              {
                "message": "User does not have credentials",
                "domain": "global",
                "reason": "authError",
                "location": "Authorization",
                "locationType": "header"
              }
            ]
          }
        }
    '''

    return response(status_code=HTTPStatus.UNAUTHORIZED, content=content)


def fake_get_role_assignments():
    path = TEST_DIR / 'raw_roles_assignments_list.json'
    return open(path, 'r').read()


def fake_get_roles_list():
    path = TEST_DIR / 'raw_roles_list.json'
    return open(path, 'r').read()


def fake_empty_users_next_page():
    path = TEST_DIR / 'raw_empty_users_next_page_response.json'
    return open(path, 'r').read()


def fake_users():
    path = TEST_DIR / 'raw_users_response.json'
    return open(path, 'r').read()
