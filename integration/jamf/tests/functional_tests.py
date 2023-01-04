from pathlib import Path
from unittest import mock

import pytest

from integration import jamf
from integration.account import set_connection_account_number_of_records
from integration.exceptions import ConfigurationError
from integration.jamf import implementation
from integration.jamf.implementation import N_RECORDS, encrypt_password_if_not_encrypted
from integration.settings import INTEGRATIONS_ENCRYPTION_KEY
from integration.tests import create_connection_account
from integration.tests.factory import (
    create_error_catalogue,
    create_integration_alert,
    get_db_number_of_records,
)
from laika.tests import mock_responses

FAKE_PASSWORD = 'fake_password'
FAKE_USERNAME = 'fake_username'
FAKE_SUBDOMAIN = 'fake_subdomain'


def load_response(file_name):
    parent_path = Path(__file__).parent
    with open(parent_path / file_name, 'r') as file:
        return file.read()


@pytest.fixture
def connection_account():
    # Omit validation for testing purpose, sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate

    # Omit validation for testing purpose, Password is not encrypted
    def omit_password_encrypt(connection_account):
        return INTEGRATIONS_ENCRYPTION_KEY

    implementation.validate_credentials = omit_password_encrypt
    responses = [
        load_response('raw_buildings_response.json'),
        load_response('raw_departments_response.json'),
        load_response('raw_computers_response.json'),
        load_response('raw_empty_devices_response.json'),
        load_response('raw_mobile_devices_response.json'),
        load_response('raw_mobile_device_detail_response.json'),
        load_response('raw_empty_devices_response.json'),
    ]
    with mock_responses(responses):
        yield jamf_connection_account()


@pytest.fixture
def connection_account_for_computer_devices_integration():
    responses = [load_response('raw_computers_response.json')]
    with mock_responses(responses):
        yield jamf_connection_account()


@pytest.fixture
def connection_account_for_auth_response():
    responses = [load_response('raw_auth_response.json')]
    with mock_responses(responses):
        yield jamf_connection_account()


@pytest.fixture
def connection_account_for_auth_with_enrollment_role_response():
    responses = [load_response('raw_auth_enrollment_type_response.json')]
    with mock_responses(responses):
        yield jamf_connection_account()


@pytest.fixture
def connection_account_for_mobile_devices_integration():
    responses = [load_response('raw_mobile_devices_response.json')]
    with mock_responses(responses):
        yield jamf_connection_account()


@pytest.mark.functional
def test_jamf_integrate_account_number_of_records(connection_account):
    implementation.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_jamf_valid_subdomain():
    valid_domain = implementation.get_valid_domain(
        'https://laikatest.jamfcloud.com/index.html'
    )
    assert valid_domain == 'laikatest'


@pytest.mark.functional
def test_jamf_invalid_subdomain():
    with pytest.raises(ConfigurationError):
        implementation.get_valid_domain('laikatest/index.html')


def jamf_connection_account(**kwargs):
    return create_connection_account(
        'Jamf',
        authentication={},
        configuration_state={
            'credentials': {
                'password': FAKE_PASSWORD,
                'username': FAKE_USERNAME,
                'subdomain': FAKE_SUBDOMAIN,
            },
        },
        **kwargs
    )


@pytest.mark.functional
def test_encrypt_password_if_not_encrypted():
    ca = jamf_connection_account()
    encrypt_password_if_not_encrypted(ca)
    assert ca.credentials['password'] != FAKE_PASSWORD


@pytest.mark.functional
@mock.patch("integration.jamf.implementation.get_valid_domain")
@mock.patch("integration.jamf.implementation.validate_credentials")
def test_encrypt_in_connect(
    get_valid_domain, validate_credentials, connection_account_for_auth_response
):
    get_valid_domain.return_value = 'mocked_domain'
    validate_credentials.return_value = 'mocked_credentials'
    jamf.connect(connection_account_for_auth_response)
    assert connection_account_for_auth_response.credentials['password'] != FAKE_PASSWORD


@pytest.mark.functional
@mock.patch("integration.jamf.implementation.get_valid_domain")
@mock.patch("integration.jamf.implementation.validate_credentials")
def test_raise_exception_not_admin_or_auditor(
    get_valid_domain,
    validate_credentials,
    connection_account_for_auth_with_enrollment_role_response,
):
    integration = connection_account_for_auth_with_enrollment_role_response.integration
    catalogue = create_error_catalogue(
        '002', 'INSUFFICIENT_PERMISSIONS', 'IS NOT ADMIN', False
    )
    create_integration_alert(integration, catalogue, '003')
    get_valid_domain.return_value = 'mocked_domain'
    validate_credentials.return_value = 'mocked_credentials'
    with pytest.raises(ConfigurationError):
        jamf.connect(connection_account_for_auth_with_enrollment_role_response)
