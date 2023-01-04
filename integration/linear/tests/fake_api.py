from pathlib import Path

from httmock import HTTMock, urlmatch

UNEXPECTED_API_OPERATION = 'Unexpected operation for Linear fake api'


def fake_linear_api():
    """This fake will intercept http calls to linear domain and
    It will use a fake implementation"""
    return HTTMock(fake_linear_services, fake_auth)


@urlmatch(netloc='api.linear.app', path='/oauth/token')
def fake_auth(url, request):
    access_token_request = 'refresh_token' in request.body
    if access_token_request:
        return '{"access_token":"token"}'
    auth_code_request = 'authorization_code' in request.body
    if auth_code_request:
        return '{"refresh_token":"token", "access_token":"token"}'
    raise ValueError(UNEXPECTED_API_OPERATION)


def load_response(filename):
    with open(Path(__file__).parent / filename, 'r') as file:
        return file.read()


@urlmatch(netloc='api.linear.app', path='/graphql')
def fake_linear_services(url, request):
    query = "".join(request.body.decode("utf-8").split("\\n"))
    if 'users' in query:
        return load_response('raw_users_response.json')
    elif 'issues' in query:
        return load_response('raw_tickets_response.json')
    elif 'projects' in query:
        return load_response('raw_projects_response.json')
    elif 'viewer' in query:
        return load_response('raw_current_user_response.json')
    raise ValueError(UNEXPECTED_API_OPERATION)
