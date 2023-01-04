import json
from pathlib import Path

import pytest

from integration.microsoft.implementation import (
    GLOBAL_ADMIN,
    MICROSOFT_SYSTEM,
    MicrosoftRequest,
    _map_device_response_to_laika_object,
    _map_user_response_to_laika_object,
)


@pytest.fixture
def user_payload():
    path = Path(__file__).parent / 'raw_users_response.json'
    user, *_ = json.loads(open(path, 'r').read())['value']
    return user


@pytest.fixture
def organization_payload():
    path = Path(__file__).parent / 'raw_organization_response.json'
    org, *_ = json.loads(open(path, 'r').read())['value']
    return org


@pytest.fixture
def groups_payload():
    path = Path(__file__).parent / 'raw_groups_by_user_response.json'
    groups, *_ = json.loads(open(path, 'r').read())['value']
    return groups


@pytest.fixture
def device_payload():
    path = Path(__file__).parent / 'raw_devices_response.json'
    device, *_ = json.loads(open(path, 'r').read())['value']
    return device


ALIAS = 'microsoft test'
SOURCE_SYSTEM = 'Source System'
CONNECTION_NAME = 'Connection Name'


def test_laika_object_user_mapping(user_payload, organization_payload, groups_payload):
    roles = [GLOBAL_ADMIN]
    groups = [group['displayName'] for group in [groups_payload]]

    user = MicrosoftRequest(groups, user_payload, [organization_payload], roles)
    expected_response = _user_expected_response()

    lo = _map_user_response_to_laika_object(user, ALIAS)
    expected = {SOURCE_SYSTEM: MICROSOFT_SYSTEM, CONNECTION_NAME: ALIAS}

    assert expected.items() < lo.items()
    assert expected_response == lo


def test_laika_object_device_mapping(device_payload):
    expected_response = _device_expected_response()
    lo = _map_device_response_to_laika_object(device_payload, ALIAS)
    assert expected_response == lo


def _user_expected_response():
    return {
        'Id': 'a9343da3-9930-415e-b6e0-ee477bfffefe',
        'First Name': 'Laika',
        'Last Name': 'dev-user',
        'Title': 'Software Engineer',
        'Email': 'laika-dev-user@laika365.onmicrosoft.com',
        'Organization Name': 'laika365',
        'Is Admin': True,
        'Roles': GLOBAL_ADMIN,
        'Mfa Enabled': '',
        'Mfa Enforced': '',
        SOURCE_SYSTEM: MICROSOFT_SYSTEM,
        CONNECTION_NAME: ALIAS,
        'Groups': 'laika365',
    }


def _device_expected_response():
    return {
        'Id': '132870e6-102e-496b-a73b-13be39818ddb',
        'Name': 'laika-admin365_Android_7/16/2022_7:06 PM',
        'Device Type': 'Mobile',
        'Company Issued': False,
        'Serial Number': 'N/A',
        'Model': 'sdk_gphone64_x86_64',
        'Brand': 'Google',
        'Operating System': 'Android',
        'OS Version': '12.0',
        'Location': 'Workplace',
        'Owner': 'test test',
        'Issuance Status': 'N/A',
        'Anti Virus Status': 'N/A',
        'Purchased On': None,
        'Cost': None,
        'Note': 'N/A',
        'Encryption Status': 'N/A',
        SOURCE_SYSTEM: MICROSOFT_SYSTEM,
        CONNECTION_NAME: ALIAS,
    }
