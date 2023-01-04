from pathlib import Path

from httmock import HTTMock, response, urlmatch

PARENT_PATH = Path(__file__).parent


def fake_okta_api():
    return HTTMock(_fake_okta_api)


def factors_response():
    path = PARENT_PATH / 'raw_factors_response.json'
    return open(path, 'r').read()


def roles_response():
    path = PARENT_PATH / 'raw_roles_response.json'
    return open(path, 'r').read()


def groups_response():
    path = PARENT_PATH / 'raw_groups_response.json'
    return open(path, 'r').read()


def apps_response():
    path = PARENT_PATH / 'raw_apps_response.json'
    return open(path, 'r').read()


def users_response():
    path = PARENT_PATH / 'raw_users_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='test.okta.com')
def _fake_okta_api(url, request):
    if 'users' in url.path:
        if 'groups' in url.path:
            return http_mock_response(groups_response())
        if 'appLinks' in url.path:
            return http_mock_response(apps_response())

        return http_mock_response(users_response())

    if 'groups' in url.path:
        return http_mock_response(groups_response())

    raise ValueError('Unexpected operation for okta fake api')


def http_mock_response(data):
    headers = {'x-rate-limit-remaining': '100', 'x-rate-limit-reset': '1'}
    return response(status_code=200, content=data, headers=headers)


def http_mock_response_rate_limit(data):
    headers = {'x-rate-limit-remaining': '0', 'x-rate-limit-reset': '1'}
    return response(status_code=429, content=data, headers=headers)
