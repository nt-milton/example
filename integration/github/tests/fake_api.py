import json
from datetime import datetime
from pathlib import Path

from httmock import HTTMock, urlmatch


def fake_github_api():
    """This fake will intercept http calls to github domain and
    It will use a fake implementation"""
    return HTTMock(fake_graphql, fake_authentication_api)


def fake_github_api_without_org():
    return HTTMock(fake_missing_org_validation, fake_authentication_api)


@urlmatch(netloc='github.com')
def fake_authentication_api(url, request):
    if 'access_token' in url.path:
        return _credentials()
    raise ValueError('Unexpected operation for github fake api')


@urlmatch(netloc='api.github.com')
def fake_graphql(url, request):
    query = request.body.decode()
    if 'organizations' in query:
        return _organizations()
    if 'repositories' in query:
        return _repos()
    if 'pullRequests' in query:
        return _pull_request()
    if 'membersWithRole' in query:
        return _users()
    if 'teams' in query:
        return _members_by_teams()
    raise ValueError('Unexpected operation for github fake api')


@urlmatch(netloc='api.github.com')
def fake_missing_org_validation(url, request):
    query = request.body.decode()
    if 'organizations' in query:
        return _missing_org()


def _organizations():
    path = Path(__file__).parent / 'raw_org_response.json'
    return open(path, 'r').read()


def _repos():
    path = Path(__file__).parent / 'raw_repo_response.json'
    return open(path, 'r').read()


def _pull_request():
    path = Path(__file__).parent / 'raw_pr_response.json'
    r = json.loads(open(path, 'r').read())
    prs = r['data']['organization']['repository']['pullRequests']['nodes']
    for pr in prs:
        pr['createdAt'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        pr['updatedAt'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    return json.dumps(r)


def _users():
    path = Path(__file__).parent / 'raw_user_response.json'
    return open(path, 'r').read()


def _members_by_teams():
    path = Path(__file__).parent / 'raw_organization_members_by_teams.json'
    return open(path, 'r').read()


def _credentials():
    path = Path(__file__).parent / 'raw_credentials_response.json'
    return open(path, 'r').read()


def _missing_org():
    path = Path(__file__).parent / 'raw_missing_org_response.json'
    return open(path, 'r').read()
