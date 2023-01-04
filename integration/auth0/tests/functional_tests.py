import pytest

from integration import auth0
from integration.account import set_connection_account_number_of_records
from integration.auth0.implementation import AUTH0_SYSTEM
from integration.auth0.tests.fake_api import (
    fake_auth0_api,
    fake_auth0_api_insufficient_permissions,
)
from integration.encryption_utils import decrypt_value
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError
from integration.models import ConnectionAccount
from integration.okta.implementation import N_RECORDS
from integration.tests import create_connection_account
from integration.tests.factory import create_error_catalogue, get_db_number_of_records

FAKE_TOKEN = 'tests-token'
CLIENT_ID = 'clientID'
CLIENT_SECRET = 'clientSecret'
IDENTIFIER = 'identifier'
DOMAIN = 'tests.auth0.com'


@pytest.fixture
def connection_account():
    with fake_auth0_api():
        yield auth0_connection_account()


@pytest.fixture
def connection_account_insufficient_permissions():
    with fake_auth0_api_insufficient_permissions():
        yield auth0_connection_account()


@pytest.mark.functional
def test_auth0_integrate_account_number_of_records(connection_account):
    auth0.implementation.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_auth0_connect(connection_account):
    auth0.implementation.connect(connection_account)
    ca = ConnectionAccount.objects.get(id=connection_account.id)
    assert ca.status == 'pending'


@pytest.mark.functional
def test_auth0_connect_with_error(connection_account_insufficient_permissions):
    create_error_catalogue(USER_INPUT_ERROR)
    with pytest.raises(ConfigurationError):
        auth0.implementation.connect(connection_account_insufficient_permissions)


@pytest.mark.functional
def test_encrypt_password_if_not_encrypted(connection_account):
    unencrypted_client_secret = connection_account.credentials['clientSecret']
    unencrypted_access_token = connection_account.access_token
    auth0.implementation.run(connection_account)
    encrypted_access_token = connection_account.access_token
    encrypted_client_secret = connection_account.credentials['clientSecret']
    assert unencrypted_access_token == decrypt_value(encrypted_access_token)
    assert unencrypted_client_secret == decrypt_value(encrypted_client_secret)


def auth0_connection_account(**kwargs):
    return create_connection_account(
        AUTH0_SYSTEM,
        configuration_state=dict(
            credentials={
                'clientID': CLIENT_ID,
                'clientSecret': CLIENT_SECRET,
                'identifier': IDENTIFIER,
                'domain': DOMAIN,
            },
        ),
        authentication={
            'access_token': (
                'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVC'
                'IsImtpZCI6InJud3d2d1BnOVhuMFVpbzJKLVNMVCJ9'
            )
        },
        **kwargs
    )
