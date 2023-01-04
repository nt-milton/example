import json
from datetime import datetime
from pathlib import Path

import pytest

from integration.datadog.implementation import DATADOG_SYSTEM
from integration.datadog.mapper import (
    map_event_response_to_laika_object,
    map_monitor_response_to_laika_object,
)


@pytest.fixture
def monitor_payload():
    path = Path(__file__).parent / 'raw_monitor_response.json'
    monitor, *_ = json.loads(open(path, 'r').read())
    return monitor


@pytest.fixture
def event_payload():
    path = Path(__file__).parent / 'raw_events_response.json'
    event, *_ = json.loads(open(path, 'r').read())['events']
    return event


def test_laika_object_mapping_monitor_from_datadog_monitor(monitor_payload):
    alias = 'testing_account'
    got = map_monitor_response_to_laika_object(monitor_payload, alias)
    expected = {
        'Id': str(monitor_payload['id']),
        'Name': monitor_payload['name'],
        'Type': monitor_payload['type'],
        'Query': monitor_payload['query'],
        'Message': monitor_payload['message'],
        'Overall State': monitor_payload['overall_state'],
        'Created At': monitor_payload['created'],
        'Created By (Name)': monitor_payload['creator']['name'],
        'Created By (Email)': monitor_payload['creator']['email'],
        'Tags': ','.join(monitor_payload.get('tags', [])),
        'Destination': (
            'Emails: (test@mail.com), Slack: (@slack-staging-alerts), Other:'
            ' (@sns-notification-alerts)'
        ),
        'Notification Type': 'Email, Slack, Other',
        'Connection Name': alias,
        'Source System': DATADOG_SYSTEM,
    }
    assert got == expected


def test_laika_object_mapping_event_from_datadog_event(event_payload):
    alias = 'testing_account'
    got = map_event_response_to_laika_object(event_payload, alias)
    expected = {
        'Id': str(event_payload['id']),
        'Title': event_payload['title'],
        'Text': event_payload['text'],
        'Type': event_payload['alert_type'],
        'Priority': event_payload['priority'],
        'Host': event_payload.get('host', ''),
        'Device': event_payload['device_name'],
        'Source': event_payload['source'],
        'Tags': ','.join(event_payload.get('tags', [])),
        'Event date': datetime.fromtimestamp(
            event_payload['date_happened']
        ).isoformat(),
        'Connection Name': alias,
        'Source System': DATADOG_SYSTEM,
    }
    assert got == expected
