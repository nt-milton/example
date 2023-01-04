import json
from pathlib import Path

import pytest

from integration.vetty.implementation import VETTY_SYSTEM, _map_background_checks

TEST_DIR = Path(__file__).parent
ALIAS = 'vetty test'


@pytest.fixture
def background_checks_payload():
    path = TEST_DIR / 'raw_background_checks.json'
    response = open(path, 'r').read()
    return json.loads(response)


@pytest.mark.django_db
def test_laika_object_background_checks_mapping(background_checks_payload):
    background_check = background_checks_payload[0]
    expected_response = _background_check_expected_response()

    lo = _map_background_checks(background_check, ALIAS)
    expected = {'Source System': VETTY_SYSTEM, 'Connection Name': ALIAS}

    assert expected.items() < lo.items()
    assert expected_response == lo


def _background_check_expected_response():
    return {
        'Id': 'testid1',
        'First Name': 'test',
        'Last Name': 'applicant',
        'Email': 'test@heylaika.com',
        'Check Name': 'Test Package',
        'Status': 'in_progress',
        'Source System': VETTY_SYSTEM,
        'Connection Name': ALIAS,
        'Estimated Completion Date': None,
        'Initiation Date': None,
        'Link to People Table': None,
        'Package': 'Test Package',
    }
