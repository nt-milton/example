import pytest as pytest

from integration.integration_utils.finch_utils import verify_finch_request_id
from integration.integration_utils.google_utils import (
    convert_base64_to_json,
    get_json_credentials,
)
from integration.models import SUCCESS
from integration.tests import create_connection_account


@pytest.mark.functional
def test_convert_base64_to_json(test_data):
    json_file = convert_base64_to_json(test_data)
    assert json_file['type'] == 'service_account'
    assert json_file['test'] == 'json'


@pytest.mark.functional
def test_convert_base64_to_json_error(test_data_error):
    with pytest.raises(ValueError):
        convert_base64_to_json(test_data_error)


@pytest.mark.functional
def test_get_credentials_file(graphql_organization, test_data_file):
    connection = create_connection_account(
        'test-json-credentials',
        configuration_state={'credentials': {"credentialsFile": test_data_file}},
        status=SUCCESS,
        organization=graphql_organization,
    )
    json_credentials = get_json_credentials(connection)
    assert json_credentials['type'] == 'service_account'
    assert json_credentials['test'] == 'json'


@pytest.fixture()
def test_data_file():
    return [
        {
            "name": "test",
            "file": "ewoidHlwZSI6ICJzZXJ2aWNlX2FjY291bnQiLAogInRlc3QiOiJqc29uIgp9",
        }
    ]


@pytest.fixture()
def test_data():
    return "ewoidHlwZSI6ICJzZXJ2aWNlX2FjY291bnQiLAogInRlc3QiOiJqc29uIgp9"


@pytest.fixture()
def test_data_error():
    return [{"name": "test", "file": "535934593495934534"}]


@pytest.mark.functional()
def test_validate_finch_request_id():
    headers = {
        'Date': 'Mon, 27 Jul 2009 12:28:53 GMT',
        'Server': 'Apache/2.2.14 (Win32)',
        'Last-Modified': 'Wed, 22 Jul 2009 19:15:56 GMT',
        'Content-Length': '88',
        'Connection': 'Closed',
        'Finch-Request-Id': 'e5719fd0-aa22-42b3-a22c-638b5bd0c9c8',
    }
    value = verify_finch_request_id(headers)
    assert str(value) == headers.get('Finch-Request-Id')


@pytest.mark.functional()
def test_validate_finch_request_id_none():
    value = verify_finch_request_id({'Finch-Request-Id': 'test'})
    assert value is None
