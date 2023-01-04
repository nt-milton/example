import json
from pathlib import Path

import pytest

from integration.jira.implementation import JIRA_SYSTEM, build_map_change_requests

CONNECTION_NAME = 'test account'


@pytest.fixture
def ticket_payload():
    path = Path(__file__).parent / 'raw_tickets_response.json'
    user, *_ = json.loads(open(path, 'r').read())['issues']
    return user


@pytest.fixture
def map_function():
    return build_map_change_requests('customfield_10014')


def test_laika_object_empty_approver_for_missing_author(ticket_payload, map_function):
    history, *_ = ticket_payload['changelog']['histories']
    history.pop('author')

    lo = map_function(ticket_payload, CONNECTION_NAME)

    expected = {'Approver': None}
    assert expected.items() <= lo.items()


def test_laika_object_mapping_contains_source_account(ticket_payload, map_function):
    lo = map_function(ticket_payload, CONNECTION_NAME)
    expected = {'Source System': JIRA_SYSTEM, 'Connection Name': CONNECTION_NAME}
    assert expected.items() <= lo.items()


def test_laika_object_mapping_contains_epic(ticket_payload, map_function):
    lo = map_function(ticket_payload, CONNECTION_NAME)
    expected = {'Epic': 'LK-2184'}
    assert expected.items() <= lo.items()
