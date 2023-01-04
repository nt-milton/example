from pathlib import Path

from httmock import HTTMock, urlmatch

PARENT_PATH = Path(__file__).parent


def fake_microsoft_api():
    """This fake will intercept http calls to microsoft domain and
    It will use a fake implementation"""
    return HTTMock(_fake_microsoft_api, _authentication)


def fake_microsoft_api_with_error():
    return HTTMock(_sign_ins_none)


@urlmatch(netloc='graph.microsoft.com')
def _fake_microsoft_api(url, request):
    if 'groups' in url.path:
        if 'members' in url.path:
            return users()
        return _groups()
    elif 'organization' in url.path:
        return _organization()
    elif 'memberOf' in url.path:
        return _groups_by_user()
    elif 'signIns' in url.path:
        return _sign_ins()
    elif 'devices' in url.path:
        return _devices()

    raise ValueError('Unexpected operation for microsoft 365 fake api')


def _groups():
    path = PARENT_PATH / 'raw_groups_response.json'
    return open(path, 'r').read()


def users():
    path = PARENT_PATH / 'raw_users_response.json'
    return open(path, 'r').read()


def _groups_by_user():
    path = PARENT_PATH / 'raw_groups_by_user_response.json'
    return open(path, 'r').read()


def _organization():
    path = PARENT_PATH / 'raw_organization_response.json'
    return open(path, 'r').read()


def _devices():
    path = PARENT_PATH / 'raw_devices_response.json'
    return open(path, 'r').read()


def resource_not_found_response():
    path = PARENT_PATH / 'raw_resource_not_found.json'
    return open(path, 'r').read()


@urlmatch(netloc='login.microsoftonline.com')
def _authentication(url, request):
    path = PARENT_PATH / 'raw_authentication_response.json'
    return open(path, 'r').read()


def _sign_ins():
    raw_sign_ins_path = PARENT_PATH / 'raw_sign_ins_response.json'
    raw_sign_ins = open(raw_sign_ins_path, 'r').read()
    return raw_sign_ins


@urlmatch(netloc='login.microsoftonline.com')
def _sign_ins_none():
    return None
