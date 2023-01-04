import json
from pathlib import Path

import pytest

from integration.shortcut.implementation import (
    CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE,
    SHORTCUT_SYSTEM,
    build_mapper,
    map_raw_transitions_and_approver,
    map_users_to_laika_object,
)
from integration.shortcut.rest_client import RawChangeRequest
from integration.utils import get_first_last_name

PARENT_PATH = Path(__file__).parent
PROJECT_NAME = 'API SERVER'
EPIC_NAME = 'EPIC TEST'
USERNAME = 'Dev Team'
DEVELOPMENT = 'In Development'
COMPLETED = 'Completed'


@pytest.fixture
def user_payload():
    path = PARENT_PATH / 'raw_users_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def history_payload():
    path = PARENT_PATH / 'raw_story_history_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def change_request_payload():
    path = PARENT_PATH / 'raw_change_request_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def history_without_member_payload():
    path = PARENT_PATH / 'raw_history_missing_member_id.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def members():
    return {'5fe0fbb3-88b9-408e-b601-de8890cdddcd': USERNAME}


@pytest.fixture
def map_function(members):
    projects = {2: PROJECT_NAME}
    epics = {15: EPIC_NAME}
    wf_states = {500000006: DEVELOPMENT, 500000011: COMPLETED}
    return build_mapper(projects, epics, members, wf_states)


@pytest.fixture
def change_request_expected():
    path = PARENT_PATH / 'raw_change_request_map.json'
    return json.loads(open(path, 'r').read())


def test_laika_object_mapping_user(user_payload):
    alias = 'testing_account'
    user, *_ = user_payload
    got = map_users_to_laika_object(user, alias)
    first_name, last_name = get_first_last_name(user['profile']['name'])
    expected = {
        'Id': user['id'],
        'First Name': first_name,
        'Last Name': last_name,
        'Email': user['profile']['email_address'],
        'Is Admin': user['role'] == 'owner',
        'Title': None,
        'Organization Name': None,
        'Roles': '',
        'Groups': '',
        'Mfa Enabled': user['profile']['two_factor_auth_activated'],
        'Mfa Enforced': None,
        'Source System': SHORTCUT_SYSTEM,
        'Connection Name': alias,
    }
    assert got == expected


def test_laika_object_mapping_deleted_user(user_payload):
    alias = 'testing_account'
    deleted_user_index = 1
    got = map_users_to_laika_object(user_payload[deleted_user_index], alias)
    assert got['Mfa Enabled'] is None


def test_laika_object_mapping_change_request(
    change_request_payload, map_function, history_payload, members
):
    alias = 'testing_account'
    raw_cr = change_request_payload[0]
    got = map_function(RawChangeRequest(data=raw_cr, histories=history_payload), alias)
    transitions, _ = map_raw_transitions_and_approver(history_payload, members)
    expected = {
        'Key': f'ch{raw_cr["id"]}',
        'Title': raw_cr['name'],
        'Description': raw_cr['description'],
        'Issue Type': raw_cr['story_type'],
        'Epic': EPIC_NAME,
        'Project': PROJECT_NAME,
        'Assignee': USERNAME,
        'Reporter': USERNAME,
        'Status': COMPLETED,
        'Approver': USERNAME,
        'Started': raw_cr['started_at'],
        'Transitions History': {
            'template': CHANGE_REQUEST_TRANSITIONS_HISTORY_TEMPLATE,
            'data': transitions,
        },
        'Ended': raw_cr['completed_at'],
        'Url': raw_cr['app_url'],
        'Source System': SHORTCUT_SYSTEM,
        'Connection Name': alias,
    }
    assert got == expected


def test_missing_member_change_request(
    change_request_payload, map_function, history_payload
):
    alias = 'testing_account'
    raw_cr = change_request_payload[0]
    history_payload = history_payload[:-1]
    got = map_function(RawChangeRequest(data=raw_cr, histories=history_payload), alias)
    assert not got['Approver']


def test_laika_object_mapping_change_request_missing_member(
    change_request_payload,
    map_function,
    members,
    change_request_expected,
    history_without_member_payload,
):
    data = change_request_expected
    alias = 'testing_account'
    raw_cr = change_request_payload[0]
    got = map_function(
        RawChangeRequest(data=raw_cr, histories=history_without_member_payload), alias
    )
    transitions, _ = map_raw_transitions_and_approver(
        history_without_member_payload, members
    )
    expected = change_request_expected
    expected_transitions = data['Transitions History']['data']
    assert transitions == expected_transitions
    assert got == expected
