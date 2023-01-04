import pytest as pytest

from integration.account import set_connection_account_number_of_records
from integration.encryption_utils import decrypt_value
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.models import ConnectionAccount
from integration.tests import create_connection_account
from integration.tests.factory import create_error_catalogue, get_db_number_of_records
from integration.vetty import implementation
from integration.vetty.implementation import N_RECORDS
from integration.vetty.tests.fake_api import (
    fake_vetty_api,
    fake_vetty_api_missing_credential,
)
from user.tests import create_user

BACKGROUND_CHECK = 'Background Check'


@pytest.fixture
def connection_account():
    with fake_vetty_api():
        yield vetty_connection_account()


@pytest.fixture
def connection_account_error_response():
    with fake_vetty_api_missing_credential():
        yield vetty_connection_account()


@pytest.mark.functional
def test_vetty_integration_connect(connection_account):
    implementation.connect(connection_account)
    new_connection_account = ConnectionAccount.objects.get(id=connection_account.id)
    api_key = new_connection_account.configuration_state['credentials']['apiKey']
    assert decrypt_value(api_key) == 'test-api-key'


@pytest.mark.functional
def test_vetty_error_api_invalid_credential_response(connection_account_error_response):
    create_error_catalogue(USER_INPUT_ERROR)
    with pytest.raises(ConfigurationError):
        implementation.connect(connection_account_error_response)


@pytest.mark.functional
def test_vetty_integrate_account_number_of_records(connection_account):
    implementation.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_raise_if_is_duplicate(connection_account):
    created_by = create_user(
        connection_account.organization, email='heylaika+test+vetty+ca@heylaika.com'
    )
    create_connection_account(
        'Vetty-2',
        authentication={},
        organization=connection_account.organization,
        integration=connection_account.integration,
        created_by=created_by,
        configuration_state={'credentials': {'apiKey': 'test-api-key'}},
    )
    with pytest.raises(ConnectionAlreadyExists):
        implementation.run(connection_account)


def vetty_connection_account(**kwargs):
    return create_connection_account(
        'Vetty',
        authentication={},
        configuration_state={'credentials': {'apiKey': 'test-api-key'}},
        **kwargs
    )
