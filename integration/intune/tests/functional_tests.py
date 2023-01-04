import pytest

from integration import intune
from integration.account import set_connection_account_number_of_records
from integration.exceptions import ConfigurationError
from integration.intune.implementation import MICROSOFT_INTUNE, N_RECORDS
from integration.intune.tests.fake_api import fake_microsoft_intune_api
from integration.tests import create_connection_account
from integration.tests.factory import get_db_number_of_records


@pytest.fixture
def connection_account(mock_renew_token):
    with fake_microsoft_intune_api():
        yield microsoft_intune_connection_account()


@pytest.mark.functional
def test_microsoft_intune_denial_of_consent_validation(connection_account):
    with pytest.raises(ConfigurationError):
        intune.callback(None, 'redirect_uri', connection_account)


@pytest.mark.functional
def test_microsoft_intune_integrate_account_number_of_records(connection_account):
    intune.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


def microsoft_intune_connection_account(**kwargs):
    return create_connection_account(
        MICROSOFT_INTUNE,
        authentication=dict(access_token="TEST_TOKEN", refresh_token="TEST_TOKEN"),
        **kwargs,
    )
