from pathlib import Path

from httmock import HTTMock, urlmatch

PARENT_PATH = Path(__file__).parent


def fake_auth0_api():
    return HTTMock(_fake_auth0_api)


def fake_auth0_api_insufficient_permissions():
    return HTTMock(_fake_auth0_api_insufficient_permissions)


def user_roles_response():
    path = PARENT_PATH / 'raw_user_roles_response.json'
    return open(path, 'r').read()


def user_organizations_response():
    path = PARENT_PATH / 'raw_user_organizations_response.json'
    return open(path, 'r').read()


def users_response():
    path = PARENT_PATH / 'raw_users_response.json'
    return open(path, 'r').read()


def credentials_response():
    path = PARENT_PATH / 'raw_credentials_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='tests.auth0.com')
def _fake_auth0_api_insufficient_permissions(*args):
    path = PARENT_PATH / 'raw_insufficient_permissions_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='tests.auth0.com')
def _fake_auth0_api(url, request):
    if '/oauth/token' in url.path:
        return credentials_response()
    if 'users' in url.path:
        if 'organizations' in url.path:
            return user_organizations_response()
        if 'roles' in url.path:
            return user_roles_response()
        return users_response()

    raise ValueError('Unexpected operation for auth0 fake api')
