import re
from pathlib import Path

from httmock import HTTMock, urlmatch


def fake_bitbucket_api():
    """This fake will intercept http calls to github domain and
    It will use a fake implementation"""
    return HTTMock(_fake_bitbucket_api, _fake_bitbucket_oauth)


def _load_response(file_name):
    parent_path = Path(__file__).parent
    with open(parent_path / file_name, 'r') as file:
        return file.read()


@urlmatch(netloc='bitbucket.org')
def _fake_bitbucket_oauth(url, request):
    if 'access_token' in url.path:
        return _load_response('get_refresh_token.json')
    raise ValueError('Unexpected operation for github fake api')


@urlmatch(netloc='api.bitbucket.org')
def _fake_bitbucket_api(url, request):
    if re.search('workspaces$', url.path):
        return _load_response('get_workspaces.json')
    elif re.search('workspaces/[^/]*/members$', url.path):
        return _load_response('get_workspace_members.json')
    elif re.search('workspaces/[^/]*/members/[^/]*$', url.path):
        return _load_response('get_individual_member.json')
    elif re.search('users/[^/]*$', url.path):
        return _load_response('get_user.json')
    elif re.search('repositories/[^/]*$', url.path):
        return _load_response('get_repositories.json')
    elif re.search('repositories/[^/]*/[^/]*/pullrequests$', url.path):
        return _load_response('get_pull_requests.json')
    elif re.search('repositories/[^/]*/[^/]*/pullrequests/[^/]*/activity$', url.path):
        return _load_response('get_activity.json')
    raise ValueError('Unexpected operation for bitbucket fake api')
