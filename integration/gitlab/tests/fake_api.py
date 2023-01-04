from pathlib import Path

from httmock import HTTMock, urlmatch

PARENT_PATH = Path(__file__).parent


def fake_gitlab_api():
    """This fake will intercept http calls to github domain and
    It will use a fake implementation"""
    return HTTMock(fake_graphql)


def fake_gitlab_self_hosted_api():
    """This fake will intercept http calls to gitlab domain and
    It will use a fake implementation"""
    return HTTMock(fake_graphql_self_hosted)


@urlmatch(netloc='gitlab.com')
def fake_graphql(url, request):
    if url.path == '/oauth/token':
        return _authentication()
    query = request.body.decode('utf-8')
    users = 'groupMembers'
    groups = 'currentUser'
    merge_requests = 'mergeRequests'
    projects = 'projects'
    if groups in query:
        return _groups()
    elif users in query:
        return _users(query)
    elif merge_requests in query:
        return _merge_request()
    elif projects in query:
        return _projects()
    raise ValueError('Unexpected operation for gitlab fake api')


@urlmatch(netloc='gitlab.development.heylaika.com')
def fake_graphql_self_hosted(url, request):
    if url.path == '/oauth/token':
        return _authentication()
    query = request.body.decode('utf-8')
    users = 'groupMembers'
    groups = 'currentUser'
    admin_users = 'users'
    projects = 'projects'
    if groups in query:
        return _groups()
    elif users in query:
        return _users(query)
    elif admin_users in query:
        return _admin_users()
    elif projects in query:
        return _projects()
    raise ValueError('Unexpected operation for gitlab fake api')


def _groups():
    path = PARENT_PATH / 'raw_group_response.json'
    return open(path, 'r').read()


def _users(query):
    if 'laika-test-one' in query:
        path = PARENT_PATH / 'raw_users_per_group_one_response.json'
    else:
        path = PARENT_PATH / 'raw_users_per_group_two_response.json'
    return open(path, 'r').read()


def _merge_request():
    path = PARENT_PATH / 'raw_merge_response.json'
    return open(path, 'r').read()


def _projects():
    path = PARENT_PATH / 'raw_project_response.json'
    return open(path, 'r').read()


def _admin_users():
    path = PARENT_PATH / 'raw_admin_users_response.json'
    return open(path, 'r').read()


def _authentication():
    path = PARENT_PATH / 'raw_authentication_response.json'
    return open(path, 'r').read()
