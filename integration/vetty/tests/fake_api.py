from pathlib import Path

from httmock import HTTMock, response, urlmatch

TEST_DIR = Path(__file__).parent


def fake_vetty_api():
    return HTTMock(_fake_vetty_resources_api)


def fake_vetty_api_missing_credential():
    return HTTMock(_fake_auth_response_without_api_key)


@urlmatch(netloc='api.vetty.co')
def _fake_vetty_resources_api(url, request):
    if 'applicants' in url.path:
        return applicants_response()
    if 'packages' in url.path:
        return packages_response()
    if 'screenings' in url.path:
        return screening_response()
    raise ValueError('Unexpected operation for vetty  fake api')


def screening_response():
    path = TEST_DIR / 'raw_screening_response.json'
    return open(path, 'r').read()


def packages_response():
    path = TEST_DIR / 'raw_packages_response.json'
    return open(path, 'r').read()


def applicants_response():
    path = TEST_DIR / 'raw_applicants_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='api.vetty.co')
def _fake_auth_response_without_api_key(url, request):
    path = TEST_DIR / 'raw_missing_authorization.json'
    api_response = open(path, 'r').read()
    headers = {'Content-Type': 'application/json'}
    return response(401, api_response, headers)
