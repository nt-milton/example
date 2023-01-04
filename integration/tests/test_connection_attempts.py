from datetime import date, datetime, timedelta
from unittest import mock

import pytest
from freezegun.api import freeze_time

from integration.error_codes import (
    BAD_CLIENT_CREDENTIALS,
    DENIAL_OF_CONSENT,
    INSUFFICIENT_PERMISSIONS,
    MISSING_GITHUB_ORGANIZATION,
    OTHER,
    USER_INPUT_ERROR,
)
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.factory import normalize_integration_name
from integration.models import ALREADY_EXISTS, ERROR, SUCCESS, SYNC, ConnectionAccount
from integration.tests.factory import create_connection_account, create_error_catalogue
from integration.utils import wizard_error
from organization.models import Organization

DUMMY_ERROR = 'Dummy error'

CURRENT_TIME = datetime(2020, 3, 15)


@pytest.fixture
def connection_account(graphql_organization):
    connection_account = create_connection_account(
        vendor_name='Vendor Test',
        alias='Connection 1',
        organization=graphql_organization,
    )
    connection_account.save = mock.Mock(return_value=None)
    return connection_account


@pytest.fixture
def error_connection_account():
    connection_account = create_connection_account(
        vendor_name='Vendor Test',
        alias='Connection 1',
        status=ERROR,
        result={
            'error_response': {"error": "test-error"},
            'email_sent': str(date.today()),
            'wizard_status': {'status': 'error', 'wizard': 'INCOMPLETE'},
        },
    )
    connection_account.save = mock.Mock(return_value=None)
    return connection_account


@pytest.mark.functional
def test_connection_attempt_success(connection_account):
    with connection_account.connection_attempt():
        # Does not require implementation
        pass
    assert connection_account.status == SUCCESS


@pytest.mark.functional
@freeze_time(CURRENT_TIME)
def test_connection_attempt_saves_last_run(connection_account: ConnectionAccount):
    with connection_account.connection_attempt():
        # Does not require implementation
        pass
    last_run = connection_account.configuration_state.get('last_successful_run')
    assert last_run is not None
    assert last_run == CURRENT_TIME.timestamp()


@pytest.mark.functional
def test_connection_attempt_error_dont_saves_last_run(
    connection_account: ConnectionAccount,
):
    with pytest.raises(ValueError):
        with connection_account.connection_attempt():
            raise ValueError(DUMMY_ERROR)

    last_run = connection_account.configuration_state.get('last_successful_run')
    assert last_run is None


@pytest.mark.functional
def test_connection_send_mail_error_field_turned_off_permanently(connection_account):
    connection_account.send_mail_error = False
    with connection_account.connection_attempt():
        # Does not require implementation
        pass
    assert connection_account.status == SUCCESS
    assert not connection_account.send_mail_error


@pytest.mark.functional
def test_connection_attempt_error(connection_account):
    with pytest.raises(ValueError):
        with connection_account.connection_attempt():
            raise ValueError(DUMMY_ERROR)
    assert connection_account.status == ERROR


@pytest.mark.functional
def test_connection_attempt_already_exists(connection_account):
    with pytest.raises(ConnectionAlreadyExists):
        with connection_account.connection_attempt():
            raise ConnectionAlreadyExists(DUMMY_ERROR)

    assert connection_account.status == ALREADY_EXISTS


@pytest.mark.functional
def test_connection_attempt_sync_status(connection_account):
    with connection_account.connection_attempt():
        assert connection_account.status == SYNC


def test_get_integration_with_whitespace():
    integration = normalize_integration_name('Google Workspace')
    assert integration == 'google_workspace'


@pytest.mark.functional
def test_get_correct_error_code_insufficient_permissions(connection_account):
    connection_account.organization = Organization()
    with pytest.raises(ConfigurationError):
        with connection_account.connection_attempt():
            raise ConfigurationError.insufficient_permission()
    assert connection_account.error_code == INSUFFICIENT_PERMISSIONS


@pytest.mark.functional
def test_email_not_sent_with_same_error_code_insufficient_permissions(
    error_connection_account,
):
    error_connection_account.error_code = INSUFFICIENT_PERMISSIONS
    with pytest.raises(ConfigurationError):
        with error_connection_account.connection_attempt():
            raise ConfigurationError.insufficient_permission()
    assert error_connection_account.error_email_already_sent()


@pytest.mark.functional
def test_email_not_sent_with_same_error_code_denial_of_consent(
    error_connection_account,
):
    error_connection_account.error_code = DENIAL_OF_CONSENT
    with pytest.raises(ConfigurationError):
        with error_connection_account.connection_attempt():
            raise ConfigurationError.denial_of_consent()
    assert error_connection_account.error_email_already_sent()


@pytest.mark.functional
def test_email_not_sent_with_same_error_code_bad_client_credentials(
    error_connection_account,
):
    error_connection_account.error_code = BAD_CLIENT_CREDENTIALS
    with pytest.raises(ConfigurationError):
        with error_connection_account.connection_attempt():
            raise ConfigurationError.bad_client_credentials()
    assert error_connection_account.error_email_already_sent()


@pytest.mark.functional
def test_email_not_sent_same_day(error_connection_account):
    with pytest.raises(ConfigurationError):
        with error_connection_account.connection_attempt():
            raise ConfigurationError.bad_client_credentials()
    assert error_connection_account.error_email_already_sent()


@pytest.mark.functional
def test_email_sent_different_day_different_error_code(error_connection_account):
    error_connection_account.error_code = INSUFFICIENT_PERMISSIONS
    with pytest.raises(ConfigurationError):
        with error_connection_account.connection_attempt():
            raise ConfigurationError.bad_client_credentials()
    error_connection_account.result['email_sent'] = str(
        date.today() - timedelta(days=1)
    )
    error_connection_account.save()
    assert error_connection_account.error_email_already_sent()


@pytest.mark.functional
def test_email_sent(connection_account):
    connection_account.error_code = BAD_CLIENT_CREDENTIALS
    with pytest.raises(ConfigurationError):
        with connection_account.connection_attempt():
            raise ConfigurationError.bad_client_credentials()
    assert not connection_account.error_email_already_sent()


@pytest.mark.functional
def test_correct_error_code_missing_github_organization(connection_account):
    connection_account.organization = Organization()
    with pytest.raises(ConfigurationError):
        with connection_account.connection_attempt():
            raise ConfigurationError.missing_github_organization()
    assert connection_account.error_code == MISSING_GITHUB_ORGANIZATION


@pytest.mark.functional
def test_connection_error_with_invalid_credentials(connection_account):
    connection_account.organization = Organization()
    create_error_catalogue(BAD_CLIENT_CREDENTIALS)
    provider_error = {"error": "test-error"}
    with pytest.raises(ConfigurationError):
        with connection_account.connection_error():
            raise ConfigurationError.bad_client_credentials(response=provider_error)
    expected_result = {
        'error_response': str(provider_error),
    }
    assert connection_account.error_code == BAD_CLIENT_CREDENTIALS
    assert connection_account.result == expected_result


@pytest.mark.functional
def test_connection_attempt_with_user_input_error(connection_account):
    connection_account.organization = Organization()
    create_error_catalogue(USER_INPUT_ERROR)
    with pytest.raises(ConfigurationError):
        with connection_account.connection_attempt():
            raise wizard_error(connection_account, '001')
    assert connection_account.error_code == USER_INPUT_ERROR


@pytest.mark.functional
def test_connection_error_without_sending_email(connection_account):
    connection_account.organization = Organization()
    create_error_catalogue(OTHER, send_email=False)
    with pytest.raises(Exception):
        with connection_account.connection_attempt():
            raise ValueError('Error Not implemented')
    assert not connection_account.error_email_already_sent()
