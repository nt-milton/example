import json
from pathlib import Path

import pytest

from integration.sentry.implementation import (
    SENTRY_SYSTEM,
    SentryUser,
    map_event_response_to_laika_object,
    map_user_response_to_laika_object,
)
from integration.sentry.mapper import (
    build_map_monitor_response_to_laika_object,
    get_tag_list,
    name_formatted,
)

CONNECTION_NAME = 'Connection Name'
SOURCE_SYSTEM = 'Source System'


@pytest.fixture
def user_payload():
    path = Path(__file__).parent / 'raw_user_response.json'
    user = json.loads(open(path, 'r').read())
    yield SentryUser(
        user=user[0],
    )


@pytest.fixture
def monitor_payload():
    path = Path(__file__).parent / 'raw_monitor_project_1_response.json'
    monitor = json.loads(open(path, 'r').read())
    return monitor[0]


@pytest.fixture
def event_payload():
    path = Path(__file__).parent / 'raw_events_project_1_chunk_1_response.json'
    event = json.loads(open(path, 'r').read())
    return event[0]


def test_laika_object_mapping_user_from_sentry_user(user_payload):
    alias = 'testing_account'
    got = map_user_response_to_laika_object(user_payload, alias)

    expected = {
        'Id': str(user_payload.user['id']),
        'First Name': name_formatted(user_payload.user['name']).get('first_name', ''),
        'Last Name': name_formatted(user_payload.user['name']).get('last_name', ''),
        'Email': user_payload.user['email'],
        'Roles': user_payload.user['role'],
        'Is Admin': user_payload.user['user']['isSuperuser'],
        'Organization Name': user_payload.user['name'],
        'Groups': ','.join(user_payload.user.get('projects', [])),
        'Mfa Enabled': user_payload.user['user']['has2fa'],
        SOURCE_SYSTEM: SENTRY_SYSTEM,
        CONNECTION_NAME: alias,
    }

    assert got == expected


def test_laika_object_mapping_monitor_from_sentry_monitor(monitor_payload):
    monitor = monitor_payload
    alias = 'testing_account'
    got = build_map_monitor_response_to_laika_object([], [])(monitor_payload, alias)
    expected = {
        'Id': str(monitor['id']),
        'Name': monitor['name'],
        'Type': monitor['type'],
        'Query': '  ',
        'Created At': monitor['dateCreated'],
        'Created By (Name)': monitor['createdBy']['name'],
        'Created By (Email)': monitor['createdBy']['email'],
        'Notification Type': '',
        'Destination': '',
        SOURCE_SYSTEM: SENTRY_SYSTEM,
        CONNECTION_NAME: alias,
    }
    assert got == expected


def test_laika_object_mapping_event_from_sentry_event(event_payload):
    event = event_payload
    alias = 'testing_account'
    got = map_event_response_to_laika_object(event_payload, alias)
    expected = {
        'Id': str(event['id']),
        'Title': event['title'],
        'Text': event['message'],
        'Type': event['event.type'],
        'Host': event['location'],
        'Source': event['platform'],
        'Event date': event['dateCreated'],
        'Tags': ', '.join(map(get_tag_list, event['tags'])),
        SOURCE_SYSTEM: SENTRY_SYSTEM,
        CONNECTION_NAME: alias,
    }
    assert got == expected
