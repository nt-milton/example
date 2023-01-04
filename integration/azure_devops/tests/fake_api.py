from pathlib import Path

from httmock import HTTMock, urlmatch

PARENT_PATH = Path(__file__).parent


def fake_azure_devops_api():
    """This fake will intercept http calls to microsoft domain and
    It will use a fake implementation"""
    return HTTMock(
        _fake_azure_devops_dev_api, _fake_vssps_visualstudio_api, _fake_vsaex_dev_api
    )


@urlmatch(netloc='dev.azure.com')
def _fake_azure_devops_dev_api(url, request):
    if 'projects' in url.path:
        return _projects()

    if 'pullrequests' in url.path:
        if '$skip=100' in url.query:
            return '{ "value": []}'
        return _pull_requests()

    if 'repositories' in url.path:
        return _repository()

    if 'queries' in url.path:
        return _board_query()

    if 'wiql' in url.path:
        return _wiql_from_query()

    if 'workItems' in url.path:
        if 'ids' in request.url:
            return _work_items()
        if 'updates' in request.url:
            return _work_item_updates()

    raise ValueError('Unexpected operation for Azure DevOps fake api')


@urlmatch(netloc='app.vssps.visualstudio.com')
def _fake_vssps_visualstudio_api(url, request):
    if 'token' in url.path:
        return _authentication()

    if 'accounts' in url.path:
        return _organizations()

    if 'profile' in url.path:
        return _profile()


@urlmatch(netloc='vsaex.dev.azure.com')
def _fake_vsaex_dev_api(url, request):
    if '8a69cb72-aee5-6a1e-b4a5-484a56cca7e1' in url.path:
        return _users_entitlements()
    if 'skip=100' in url.query:
        return '{ "value": []}'
    return _users()


def _users():
    path = PARENT_PATH / 'raw_users_response.json'
    return open(path, 'r').read()


def _users_entitlements():
    path = PARENT_PATH / 'raw_user_entitlements_response.json'
    return open(path, 'r').read()


def _pull_requests():
    path = PARENT_PATH / 'raw_pull_request_response.json'
    return open(path, 'r').read()


def _repository():
    path = PARENT_PATH / 'raw_repository_response.json'
    return open(path, 'r').read()


def _projects():
    path = PARENT_PATH / 'raw_repository_response.json'
    return open(path, 'r').read()


def _organizations():
    path = PARENT_PATH / 'raw_organizations_response.json'
    return open(path, 'r').read()


def _profile():
    path = PARENT_PATH / 'raw_profile_response.json'
    return open(path, 'r').read()


def _authentication():
    path = PARENT_PATH / 'raw_authentication_response.json'
    return open(path, 'r').read()


def _board_query():
    path = PARENT_PATH / 'raw_board_query_by_id.json'
    return open(path, 'r').read()


def _wiql_from_query():
    path = PARENT_PATH / 'raw_wiql_from_query.json'
    return open(path, 'r').read()


def _work_items():
    path = PARENT_PATH / 'raw_work_items.json'
    return open(path, 'r').read()


def _work_item_updates():
    path = PARENT_PATH / 'raw_work_item_updates.json'
    return open(path, 'r').read()
