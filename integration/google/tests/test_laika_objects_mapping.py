import json
from pathlib import Path

import pytest

from integration.google.implementation import (
    GOOGLE_WORKSPACE_SYSTEM,
    map_user_response_to_laika_object,
)

ORGANIZATION_NAME = 'Organization Name'

EXPECTED_RESPONSE = {
    'Id': '103043315594614939856',
    'First Name': 'Danny',
    'Last Name': 'Chacón',
    'Title': '',
    'Email': 'danny@heylaika.com',
    ORGANIZATION_NAME: '',
    'Roles': '',
    'Groups': '',
    'Is Admin': True,
    'Mfa Enabled': True,
    'Mfa Enforced': True,
    'Source System': 'Google Workspace',
    'Connection Name': 'test account',
}
ALIAS = 'test account'
EXPECTED = {
    'Source System': GOOGLE_WORKSPACE_SYSTEM,
    'Connection Name': ALIAS,
}


@pytest.fixture
def user_payload():
    path = Path(__file__).parent / 'raw_users_response.json'
    user, *_ = json.loads(open(path, 'r').read())['users']
    return user


def test_laika_object_mapping_contains_source_account(user_payload):
    lo = map_user_response_to_laika_object(user_payload, ALIAS)

    assert EXPECTED.items() < lo.items()
    assert EXPECTED_RESPONSE == lo


def test_laika_object_mapping_with_organization_path(user_payload):
    user_payload['orgUnitPath'] = '/corp/sales'
    EXPECTED_RESPONSE[ORGANIZATION_NAME] = 'sales'

    lo = map_user_response_to_laika_object(user_payload, ALIAS)

    assert EXPECTED.items() < lo.items()
    assert EXPECTED_RESPONSE == lo


def test_laika_object_mapping_with_full_organization_path(user_payload):
    user_payload['orgUnitPath'] = '/corp/sales/frontline sales'
    EXPECTED_RESPONSE[ORGANIZATION_NAME] = 'frontline sales'

    lo = map_user_response_to_laika_object(user_payload, ALIAS)

    assert EXPECTED.items() < lo.items()
    assert EXPECTED_RESPONSE == lo
