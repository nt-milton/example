import json

import pytest

from integration.okta.implementation import (
    OKTA_SYSTEM,
    OktaRequest,
    _map_user_response_to_laika_object,
)
from integration.okta.tests.fake_api import (
    apps_response,
    factors_response,
    groups_response,
    users_response,
)

ALIAS = 'OKTA TEST'
SOURCE_SYSTEM = 'Source System'
CONNECTION_NAME = 'Connection Name'
expected = {SOURCE_SYSTEM: OKTA_SYSTEM, CONNECTION_NAME: ALIAS}


@pytest.fixture
def user_payload():
    user = json.loads(users_response())[0]
    apps = json.loads(apps_response())
    groups = json.loads(groups_response())
    factors = json.loads(factors_response())
    user = user_from_tuple(groups, apps, user, factors)
    return user


@pytest.fixture
def user_payload_no_mfa():
    user = json.loads(users_response())[0]
    apps = json.loads(apps_response())
    groups = json.loads(groups_response())
    factors = []
    user = user_from_tuple(groups, apps, user, factors)
    return user


def test_user_mapping(user_payload):
    expected_response = _user_expected_response()

    lo = _map_user_response_to_laika_object(user_payload, ALIAS)

    assert expected.items() < lo.items()
    assert expected_response == lo


def test_user_mapping_no_mfa(user_payload_no_mfa):
    expected_response = _user_expected_response()
    expected_response['Mfa Enabled'] = False

    lo = _map_user_response_to_laika_object(user_payload_no_mfa, ALIAS)

    assert expected.items() < lo.items()
    assert expected_response == lo


def user_from_tuple(groups, apps, user, factors):
    user = OktaRequest(user, groups, apps, factors)
    return user


def _user_expected_response():
    return {
        'Applications': 'Box, Google Apps Calendar, Google Apps Mail, Salesforce.com',
        'Connection Name': ALIAS,
        'Email': 'isaac.brock@example.com',
        'First Name': 'Isaac',
        'Groups': 'Cloud App Users, Internal App Users',
        'Id': '00ub0oNGTSWTBKOLGLNR',
        'Is Admin': '',
        'Last Name': 'Brock',
        'Mfa Enabled': True,
        'Mfa Enforced': '',
        'Organization Name': None,
        'Roles': '',
        'Source System': OKTA_SYSTEM,
        'Title': None,
    }
