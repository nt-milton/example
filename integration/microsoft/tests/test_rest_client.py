import json
from pathlib import Path

import pytest
from httmock import response

from integration.microsoft import rest_client
from laika.tests import mock_responses

PARENT_PATH = Path(__file__).parent


@pytest.fixture
def sign_ins_invalid_response():
    path = PARENT_PATH / 'raw_tenant_error_response.json'
    return json.loads(open(path, 'r').read())


@pytest.fixture
def sign_ins_valid_response():
    path = PARENT_PATH / 'raw_sign_ins_response.json'
    return json.loads(open(path, 'r').read())


def test_sign_ins_without_p1_tenant(sign_ins_invalid_response):
    mock_response = response(status_code=403, content=sign_ins_invalid_response)
    with mock_responses([mock_response]):
        res = rest_client.get_sign_ins_names(lambda: 'fake_auth_token', '')
        assert res == []


def test_sign_ins_with_valid_tenant(sign_ins_valid_response):
    mock_response = response(status_code=200, content=sign_ins_valid_response)
    with mock_responses([mock_response, mock_response]):
        res = rest_client.get_sign_ins_names(
            lambda: 'fake_auth_token', '2021-04-15T17:06:55Z'
        )
        assert len(list(res)) > 0
