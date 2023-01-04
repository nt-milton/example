import json

import pytest

from integration.heroku.mapper import (
    HEROKU_SYSTEM,
    HerokuRequest,
    _map_user_response_to_laika_object,
)
from integration.heroku.tests.fake_api import users_response

ALIAS = 'HEROKU TEST'
SOURCE_SYSTEM = 'Source System'
CONNECTION_NAME = 'Connection Name'
expected = {SOURCE_SYSTEM: HEROKU_SYSTEM, CONNECTION_NAME: ALIAS}


@pytest.fixture
def user_payload():
    user = json.loads(users_response())[0]
    teams = ['example']
    roles = ['member', 'admin']
    return HerokuRequest(user, teams, roles)


def test_user_mapping(user_payload):
    expected_response = _user_expected_response()

    lo = _map_user_response_to_laika_object(user_payload, ALIAS)

    assert expected.items() < lo.items()
    assert expected_response == lo


def _user_expected_response():
    return {
        'Applications': None,
        'Connection Name': ALIAS,
        'Email': 'username@example.com',
        'First Name': 'Tina Edmonds',
        'Groups': 'example',
        'Id': '01234567-89ab-cdef-0123-456789abcdef',
        'Is Admin': True,
        'Last Name': '',
        'Mfa Enabled': True,
        'Mfa Enforced': '',
        'Organization Name': '',
        'Roles': 'admin, member',
        'Source System': HEROKU_SYSTEM,
        'Title': '',
    }
