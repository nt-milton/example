import re
from pathlib import Path

from httmock import HTTMock, response, urlmatch

UNEXPECTED_API_OPERATION = 'Unexpected operation for Asana fake api'


def fake_asana_api():
    """This fake will intercept http calls to google domain and
    It will use a fake implementation"""
    return HTTMock(fake_asana_services, fake_auth)


def fake_failure_asana_api():
    return HTTMock(fake_failure_asana_services, fake_auth)


def fake_no_access_asana_api():
    return HTTMock(fake_no_access_asana_services, fake_auth)


@urlmatch(netloc='app.asana.com', path='/-/oauth_token')
def fake_auth(url, request):
    access_token_request = 'refresh_token' in request.body
    if access_token_request:
        return '{"access_token":"token"}'
    auth_code_request = 'authorization_code' in request.body
    if auth_code_request:
        return '{"refresh_token":"token"}'
    raise ValueError(UNEXPECTED_API_OPERATION)


def load_response(filename):
    with open(Path(__file__).parent / filename, 'r') as file:
        return file.read()


@urlmatch(netloc='app.asana.com', path='/api')
def fake_asana_services(url, request):
    ticket_story = re.search("tasks/[0-9]+/stories$", url.path)
    if ticket_story:
        return load_response('raw_tickets_story_response.json')
    elif 'tasks' in url.path:
        return load_response('raw_tickets_response.json')
    elif 'users' in url.path:
        return load_response('raw_users_response.json')
    elif 'projects' in url.path:
        return load_response('raw_projects_response.json')
    elif 'workspaces' in url.path:
        return load_response('raw_workspaces_response.json')
    raise ValueError(UNEXPECTED_API_OPERATION)


@urlmatch(netloc='app.asana.com', path='/api')
def fake_failure_asana_services(url, request):
    if 'users' in url.path:
        json_result = load_response('raw_users_expired_token.json')
        return response(401, json_result)
    elif 'projects' in url.path:
        return load_response('raw_projects_response.json')
    elif 'workspaces' in url.path:
        return load_response('raw_workspaces_response.json')
    raise ValueError(UNEXPECTED_API_OPERATION)


@urlmatch(netloc='app.asana.com', path='/api')
def fake_no_access_asana_services(url, request):
    if 'projects' in url.path:
        json_result = load_response('raw_no_access_project.json')
        return response(403, json_result)
    raise ValueError(UNEXPECTED_API_OPERATION)
