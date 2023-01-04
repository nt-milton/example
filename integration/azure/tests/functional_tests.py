from datetime import date, timedelta
from pathlib import Path

import pytest as pytest

from integration import azure
from integration.account import set_connection_account_number_of_records
from integration.azure import implementation
from integration.azure.implementation import N_RECORDS
from integration.azure.tests.fake_api import (
    fake_azure_api,
    fake_azure_api_missing_credential,
)
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError
from integration.models import ConnectionAccount
from integration.tests import create_connection_account
from integration.tests.factory import create_error_catalogue, get_db_number_of_records

TEST_DIR = Path(__file__).parent


@pytest.fixture
def connection_account():
    with fake_azure_api():
        yield azure_connection_account()


@pytest.fixture
def connection_account_error_response():
    with fake_azure_api_missing_credential():
        yield azure_connection_account()


@pytest.fixture
def connection_account_error_api_permission():
    with fake_azure_api_missing_credential():
        yield azure_connection_account()


@pytest.mark.functional
def test_azure_error_token_response(connection_account_error_response):
    create_error_catalogue(USER_INPUT_ERROR)
    with pytest.raises(ConfigurationError):
        implementation.connect(connection_account_error_response)


@pytest.mark.functional
def test_azure_raise_send_email_error_log(
    connection_account_error_response,
):
    create_error_catalogue(USER_INPUT_ERROR)
    yesterday = date.today() - timedelta(days=1)
    # Error occurred yesterday and email was sent
    connection_account_error_response.result.update(email_sent=str(yesterday))
    connection_account_error_response.save()

    with pytest.raises(ConfigurationError):
        with connection_account_error_response.connection_error():
            implementation.connect(connection_account_error_response)

    result = connection_account_error_response.result
    # email sent in connection account changed to today
    assert result['email_sent'] == str(date.today())
    assert 'error_response' in result


@pytest.mark.functional
def test_azure_error_api_permission_response(connection_account_error_api_permission):
    create_error_catalogue(USER_INPUT_ERROR)
    with pytest.raises(ConfigurationError):
        implementation.connect(connection_account_error_api_permission)


@pytest.mark.functional
def test_azure_integration_connect(connection_account):
    implementation.connect(connection_account)
    new_connection_account = ConnectionAccount.objects.get(id=connection_account.id)
    access_token = new_connection_account.authentication['access_token']
    assert access_token == 'TEST-TOKEN'


@pytest.mark.functional
def test_azure_integrate_account_number_of_records(connection_account):
    azure.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_azure_secret_expiration(connection_account):
    azure.connect(connection_account)
    secret_expiration = connection_account.configuration_state['settings'][
        'secretExpiration'
    ]
    assert secret_expiration['endDateTime'] == '2023-04-23T06:00:00Z'
    assert secret_expiration['appName'] == 'Laika-test'


def azure_connection_account(**kwargs):
    return create_connection_account(
        'Azure',
        authentication=_fake_auth(),
        configuration_state={'credentials': {**_credentials()}, 'settings': {}},
        **kwargs
    )


def _credentials():
    return {
        'tenantId': 'TEST-TENANT',
        'subscriptionId': 'TEST-SUBSCRIPTION',
        'clientId': 'TEST-CLIENT-ID',
        'objectId': 'TEST-OBJECT-ID',
        'clientSecret': '.trTEST-CLIENT-SECRET',
        'updating': True,
    }


def _fake_auth():
    return {
        "token_type": "Bearer",
        "expires_in": 3599,
        "ext_expires_in": 3599,
        "access_token": "TEST-TOKEN",
    }


@pytest.fixture()
def error_result():
    path = TEST_DIR / 'raw_error_response.json'
    return open(path, 'r').read()
