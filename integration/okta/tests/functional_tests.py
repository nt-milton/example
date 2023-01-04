from unittest.mock import patch

import pytest

from integration import okta
from integration.account import set_connection_account_number_of_records
from integration.encryption_utils import encrypt_value
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError
from integration.models import PENDING, ConnectionAccount
from integration.okta import rest_client
from integration.okta.implementation import N_RECORDS
from integration.okta.tests.fake_api import fake_okta_api, http_mock_response_rate_limit
from integration.okta.utils import OKTA_SYSTEM
from integration.tests import create_connection_account
from integration.tests.factory import create_error_catalogue, get_db_number_of_records

FAKE_TOKEN = 'test-token'
SUBDOMAIN = 'subdomain'
API_TOKEN = 'apiToken'
SUBDOMAIN_VALUE = 'test.okta.com'


@pytest.fixture
def connection_account():
    with fake_okta_api():
        yield okta_connection_account()


@pytest.fixture
def connection_account_valid_domain():
    with fake_okta_api():
        yield okta_connection_account_with_subdomain()


@pytest.fixture
def connection_account_valid_domain_with_https():
    with fake_okta_api():
        yield okta_connection_account_with_https_subdomain()


@pytest.mark.functional
def test_okta_integrate_account_number_of_records(connection_account):
    okta.implementation.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_okta_connect(connection_account):
    okta.implementation.connect(connection_account)
    ca = ConnectionAccount.objects.get(id=connection_account.id)
    assert ca.status == 'pending'


@pytest.mark.skip()
@pytest.mark.functional
def test_okta_connect_with_error(okta_connection_account_error):
    create_error_catalogue(USER_INPUT_ERROR)
    with pytest.raises(ConfigurationError):
        okta.implementation.connect(okta_connection_account_error)


@pytest.mark.functional
def test_okta_subdomain(connection_account_valid_domain):
    okta.implementation.connect(connection_account_valid_domain)
    ca = ConnectionAccount.objects.get(id=connection_account_valid_domain.id)
    credentials = ca.configuration_state.get('credentials')
    assert credentials.get('subdomain') == 'test.okta.com'
    assert ca.status == PENDING


@pytest.mark.functional
def test_okta_subdomain_with_https(connection_account_valid_domain_with_https):
    okta.implementation.connect(connection_account_valid_domain_with_https)
    ca = ConnectionAccount.objects.get(id=connection_account_valid_domain_with_https.id)
    credentials = ca.configuration_state.get('credentials')
    assert credentials.get('subdomain') == SUBDOMAIN_VALUE
    assert ca.status == PENDING


@pytest.mark.functional
def test_okta_x_rate_limit():
    with patch('integration.okta.rest_client.time.sleep') as mock:
        rest_client.wait_if_api_limit(http_mock_response_rate_limit('{"":""}'))
        mock.assert_not_called()


def okta_connection_account(**kwargs):
    return create_connection_account(
        OKTA_SYSTEM,
        configuration_state=dict(
            credentials={SUBDOMAIN: SUBDOMAIN_VALUE, API_TOKEN: FAKE_TOKEN},
        ),
        **kwargs
    )


@pytest.fixture()
def okta_connection_account_error(**kwargs):
    return create_connection_account(
        OKTA_SYSTEM,
        configuration_state=dict(
            credentials={SUBDOMAIN: SUBDOMAIN_VALUE, API_TOKEN: FAKE_TOKEN},
        ),
        **kwargs
    )


def okta_connection_account_with_subdomain(**kwargs):
    return create_connection_account(
        OKTA_SYSTEM,
        configuration_state=dict(
            credentials={SUBDOMAIN: 'test', API_TOKEN: encrypt_value(FAKE_TOKEN)},
        ),
        **kwargs
    )


def okta_connection_account_with_https_subdomain(**kwargs):
    return create_connection_account(
        OKTA_SYSTEM,
        configuration_state=dict(
            credentials={SUBDOMAIN: 'https://test.okta.com/', API_TOKEN: FAKE_TOKEN},
        ),
        **kwargs
    )
