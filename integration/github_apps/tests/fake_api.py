import json
from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from httmock import HTTMock, response, urlmatch

FORMATE_DATE = '%Y-%m-%dT%H:%M:%SZ'


def fake_github_api():
    """This fake will intercept http calls to github domain and
    It will use a fake implementation"""
    return HTTMock(fake_graphql, fake_authentication_api)


def fake_bad_org_api():
    return HTTMock(fake_bad_org_graphql, fake_authentication_api)


def fake_bad_user_api():
    return HTTMock(fake_bad_user_graphql, fake_authentication_api)


def fake_github_api_without_org():
    return HTTMock(fake_missing_org_validation, fake_authentication_api)


@urlmatch(netloc='api.github.com')
def fake_bad_org_graphql(url, request):
    return {"status_code": 404, "content": "404 not found"}


@urlmatch(netloc='api.github.com')
def fake_bad_user_graphql(url, request):
    return _user()


@urlmatch(netloc='github.com')
def fake_authentication_api(url, request):
    if 'access_token' in url.path:
        return _credentials()
    raise ValueError('Unexpected operation for github fake api')


def _get_repository_response(query: str):
    if 'heylaika' in query:
        return _repos()
    return _repos(is_heylaika=False)


def _get_pull_request_response(query: str):
    if 'heylaika' in query:
        if 'laika-web' in query:
            return _pull_request(is_app=False)
        return _pull_request()

    if 'autobots' in query:
        if 'autobots-web' in query:
            return _pull_request(is_heylaika=False, is_app=False)
        return _pull_request(is_heylaika=False)


@urlmatch(netloc='api.github.com')
def fake_graphql(url, request):
    if 'access_tokens' in url.path:
        return http_201_response(_access_tokens())
    if 'orgs' in url.path:
        return _organization()
    if 'users' in url.path:
        return _organization()
    if 'installations' in url.path:
        return _installations()
    if 'installation' in url.path:
        return _installation_repos()
    query = request.body.decode() if request.body else []
    if 'organizations' in query:
        return _organizations()
    if 'repositories' in query:
        return _get_repository_response(query)
    if 'pullRequests' in query:
        return _get_pull_request_response(query)
    if 'membersWithRole' in query:
        return _users()
    if 'teams' in query:
        return _members_by_teams()
    search_query_pr = (
        'search' in query
        and 'repo:' in query
        and '... on PullRequest' in query
        and 'is:pr' in query
        and 'type: ISSUE' in query
    )
    if search_query_pr:
        return _search_repos()
    raise ValueError('Unexpected operation for github fake api')


@urlmatch(netloc='api.github.com')
def fake_missing_org_validation(url, request):
    query = request.body.decode()
    if 'organizations' in query:
        return _missing_org()


def _user():
    path = Path(__file__).parent / 'raw_users_response.json'
    return open(path, 'r').read()


def _organization():
    path = Path(__file__).parent / 'raw_installation_response.json'
    return open(path, 'r').read()


def _installations():
    path = Path(__file__).parent / 'raw_installations_response.json'
    return open(path, 'r').read()


def _installation_repos():
    path = Path(__file__).parent / 'raw_installation_repos_response.json'
    return open(path, 'r').read()


def _access_tokens():
    path = Path(__file__).parent / 'raw_access_token_response.json'
    return open(path, 'r').read()


def _organizations():
    path = Path(__file__).parent / 'raw_org_response.json'
    return open(path, 'r').read()


def _repos(is_heylaika=True):
    path = Path(__file__).parent
    if is_heylaika:
        path = path / 'raw_repo_response_heylaika.json'
    else:
        path = path / 'raw_repo_response_autobots.json'
    return open(path, 'r').read()


def _search_repos():
    path = Path(__file__).parent / 'raw_pr_search_reponse_page_2.json'
    return open(path, 'r').read()


def _pull_request(is_heylaika: bool = True, is_app: bool = True):
    path = Path(__file__).parent
    if is_heylaika:
        path = (
            path / 'raw_pr_response_laika_app.json'
            if is_app
            else path / 'raw_pr_response_laika_web.json'
        )
    else:
        path = (
            path / 'raw_pr_response_autobots_app.json'
            if is_app
            else path / 'raw_pr_response_autobots_web.json'
        )

    r = json.loads(open(path, 'r').read())
    prs = r['data']['organization']['repository']['pullRequests']['nodes']
    idx = 0
    for pr in prs:
        if 0 <= idx < 2:
            # PR's within the 3 semesters but not six months
            three_semesters_time = datetime.now() - relativedelta(months=17)
            pr['createdAt'] = three_semesters_time.strftime(FORMATE_DATE)
            pr['updatedAt'] = three_semesters_time.strftime(FORMATE_DATE)
            idx += 1
            continue

        if 2 <= idx < 4:
            # PR's within the six months
            gt_three_semesters_time = datetime.now() - relativedelta(months=19)
            pr['createdAt'] = gt_three_semesters_time.strftime(FORMATE_DATE)
            pr['updatedAt'] = gt_three_semesters_time.strftime(FORMATE_DATE)
            idx += 1
            continue

        yesterday_time = datetime.now() - relativedelta(days=1)
        pr['createdAt'] = yesterday_time.strftime(FORMATE_DATE)
        pr['updatedAt'] = yesterday_time.strftime(FORMATE_DATE)
        idx += 1

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


def http_201_response(data):
    return response(status_code=201, content=data)
