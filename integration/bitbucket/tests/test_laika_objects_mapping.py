import json
from pathlib import Path

import pytest

from integration.bitbucket.implementation import (
    BITBUCKET_SYSTEM,
    map_pull_request_to_laika_object,
    map_repository_to_laika_object,
    map_user_response_to_laika_object,
)

PARENT_PATH = Path(__file__).parent
SELECTED_WORKSPACES_PATH = 'get_selected_workspaces.json'
USER_PATH = 'get_user.json'
REPOSITORY_PATH = 'get_repositories.json'
PULL_REQUEST_PATH = 'get_pull_requests.json'
ACTIVITY_PATH = 'get_activity.json'
MEMBER_PATH = 'get_member.json'


@pytest.fixture
def user_payload():
    get_member_path = PARENT_PATH / MEMBER_PATH
    workspace = json.loads(open(get_member_path, 'r').read())['workspace']
    get_user_path = PARENT_PATH / USER_PATH
    user = json.loads(open(get_user_path, 'r').read())
    yield {'workspaces': [workspace], 'user': user}


@pytest.fixture
def repository_payload():
    get_workspaces_path = PARENT_PATH / SELECTED_WORKSPACES_PATH
    workspace, *_ = json.loads(open(get_workspaces_path, 'r').read())['workspaces']
    get_repository_path = PARENT_PATH / REPOSITORY_PATH
    repository = json.loads(open(get_repository_path, 'r').read())
    yield repository


@pytest.fixture
def pull_request_payload():
    get_workspaces_path = PARENT_PATH / SELECTED_WORKSPACES_PATH
    workspace, *_ = json.loads(open(get_workspaces_path, 'r').read())['workspaces']
    get_repositories_path = PARENT_PATH / REPOSITORY_PATH
    repository, *_ = json.loads(open(get_repositories_path, 'r').read())['values']
    get_pull_requests_path = PARENT_PATH / PULL_REQUEST_PATH
    pull_request, *_ = json.loads(open(get_pull_requests_path, 'r').read())['values']
    get_activity_path = PARENT_PATH / ACTIVITY_PATH
    activity = json.loads(open(get_activity_path, 'r').read())
    approvals = []
    for individual_activity in activity['values']:
        if 'approval' in individual_activity:
            approvals.append(individual_activity['approval']['user']['display_name'])
    return {
        'workspace': workspace,
        'repository': repository,
        'pull_request': pull_request,
        'approvals': list(set(approvals)),
        'pr_visibility': 'Private',
    }


COMMON_SETS = {'Connection Name': 'testing_account', 'Source System': BITBUCKET_SYSTEM}
TESTING_ALIAS = 'testing_account'


def test_mapping_missing_staff(user_payload):
    user = user_payload['user']
    user.pop('is_staff')
    got = map_user_response_to_laika_object(user_payload, TESTING_ALIAS)
    assert not got['Is Admin']


def test_laika_object_mapping_user_from_bitbucket(user_payload):
    user = user_payload['user']
    workspaces = user_payload['workspaces']
    got = map_user_response_to_laika_object(user_payload, TESTING_ALIAS)
    expected = {
        'Id': user['uuid'],
        'First Name': user['display_name'],
        'Last Name': '',
        'Email': '',
        'Is Admin': user['is_staff'],
        'Title': '',
        'Roles': '',
        'Groups': '',
        'Organization Name': ','.join(
            sorted([workspace['name'] for workspace in workspaces])
        ),
        'Mfa Enabled': False,
        'Mfa Enforced': '',
    }
    expected.update(COMMON_SETS)
    assert got == expected


def test_laika_object_mapping_pull_request_from_bitbucket(pull_request_payload):
    pull_request = pull_request_payload['pull_request']
    repository = pull_request_payload['repository']
    approvals = set(pull_request_payload['approvals'])
    pr_visibility = pull_request_payload['pr_visibility']
    got = map_pull_request_to_laika_object(pull_request_payload, TESTING_ALIAS)
    expected = {
        'Key': f"{repository['full_name']}-{pull_request['id']}",
        'Repository': repository['full_name'],
        'Repository Visibility': pr_visibility,
        'Target': pull_request['destination']['branch']['name'],
        'Source': pull_request['source']['branch']['name'],
        'State': pull_request['state'],
        'Title': pull_request['title'],
        'Is Verified': len(approvals) > 0,
        'Is Approved': len(approvals) > 0,
        'Url': (
            f"https://bitbucket.org/{repository['full_name']}"
            f"/pull-requests/{pull_request['id']}"
        ),
        'Approvers': ','.join(sorted(approvals)),
        'Reporter': pull_request['author']['nickname'],
        'Created On': pull_request['created_on'],
        'Updated On': pull_request['updated_on'],
        'Organization': repository['workspace']['name'],
    }
    expected.update(COMMON_SETS)
    assert got == expected


def test_laika_object_mapping_repository_from_bitbucket(repository_payload):
    repository = repository_payload['values'][0]
    got = map_repository_to_laika_object(repository, TESTING_ALIAS)
    expected = {
        'Name': repository['name'],
        'Organization': repository['workspace']['slug'],
        'Public URL': repository['links']['html']['href'],
        'Is Active': True,
        'Is Public': not repository['is_private'],
        'Updated At': repository['updated_on'],
        'Created At': repository['created_on'],
    }
    expected.update(COMMON_SETS)
    assert got == expected
