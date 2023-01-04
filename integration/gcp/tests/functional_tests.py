import json
from pathlib import Path
from unittest.mock import patch

import pytest as pytest

from integration.account import set_connection_account_number_of_records
from integration.constants import GCP_VENDOR, SUCCESS
from integration.gcp import implementation, run
from integration.gcp.implementation import N_RECORDS
from integration.models import PENDING
from integration.tests.factory import (
    create_connection_account,
    create_error_catalogue,
    get_db_number_of_records,
)

from ...error_codes import USER_INPUT_ERROR
from ...exceptions import ConfigurationError
from .fake_api import (
    AUTH_HTTP_REQUEST,
    CRED_WITH_SCOPES,
    SERVICE_ACCT_INFO,
    fake_authorized_http_request,
    fake_authorized_iam_permission_error,
    fake_authorized_resource_manager_error,
    fake_authorized_without_project_access,
)

TEST_DIR = Path(__file__).parent


@pytest.fixture
def connection_account():
    return gcp_connection_account()


@patch(AUTH_HTTP_REQUEST, wraps=fake_authorized_http_request)
@patch(CRED_WITH_SCOPES)
@patch(SERVICE_ACCT_INFO)
@pytest.mark.functional()
def test_gcp_integration_connect(info_mock, scopes_mock, http_mock, connection_account):
    implementation.connect(connection_account)

    assert connection_account.status == PENDING


@patch(AUTH_HTTP_REQUEST, wraps=fake_authorized_without_project_access)
@patch(CRED_WITH_SCOPES)
@patch(SERVICE_ACCT_INFO)
@pytest.mark.functional()
def test_gcp_integration_connect_without_project_access(
    info_mock, scopes_mock, http_mock, connection_account
):
    expected_project_field_data = {'projectId': 'project-gcp'}
    implementation.connect(connection_account)
    assert expected_project_field_data == connection_account.configuration_state.get(
        'project'
    )
    assert connection_account.status == PENDING


@patch(AUTH_HTTP_REQUEST, wraps=fake_authorized_resource_manager_error)
@patch(CRED_WITH_SCOPES)
@patch(SERVICE_ACCT_INFO)
@pytest.mark.functional()
def test_gcp_integration_connect_resource_manager_error(
    info_mock, scopes_mock, http_mock, connection_account
):
    create_error_catalogue(USER_INPUT_ERROR)
    error = 'The connection does not have admin privileges.'
    with pytest.raises(ConfigurationError) as ex:
        implementation.connect(connection_account)
        assert str(ex.value) == error


@patch(AUTH_HTTP_REQUEST, wraps=fake_authorized_iam_permission_error)
@patch(CRED_WITH_SCOPES)
@patch(SERVICE_ACCT_INFO)
@pytest.mark.functional()
def test_gcp_integration_connect_iam_permissions_error(
    info_mock, scopes_mock, http_mock, connection_account
):
    create_error_catalogue(USER_INPUT_ERROR)
    error = 'The connection does not have admin privileges.'
    with pytest.raises(ConfigurationError) as ex:
        implementation.connect(connection_account)
        assert str(ex.value) == error


@pytest.mark.functional()
def test_gcp_integration_invalid_credentials(connection_account):
    # By default the connection account contains an invalid
    # credentials in base64
    create_error_catalogue(USER_INPUT_ERROR)
    with pytest.raises(ConfigurationError):
        implementation.connect(connection_account)


@patch(AUTH_HTTP_REQUEST, wraps=fake_authorized_http_request)
@patch(CRED_WITH_SCOPES)
@patch(SERVICE_ACCT_INFO)
@pytest.mark.functional
def test_gcp_integrate_account_number_of_records(
    info_mock, scopes_mock, http_mock, connection_account
):
    run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@patch(AUTH_HTTP_REQUEST, wraps=fake_authorized_http_request)
@patch(CRED_WITH_SCOPES)
@patch(SERVICE_ACCT_INFO)
@pytest.mark.functional
def test_gcp_with_invalid_or_not_found_roles_should_be_success(
    info_mock, scopes_mock, http_mock, connection_account
):
    run(connection_account)
    assert connection_account.status == SUCCESS


@patch(AUTH_HTTP_REQUEST, wraps=fake_authorized_http_request)
@patch(CRED_WITH_SCOPES)
@patch(SERVICE_ACCT_INFO)
@pytest.mark.functional(permissions=['integration.view_connectionaccount'])
def test_get_google_cloud_services(
    info_mock, scopes_mock, http_mock, graphql_client, graphql_organization
):
    connection_account = create_connection_account(
        'Google Cloud Platform',
        alias='testing_connection',
        organization=graphql_organization,
        authentication={},
        configuration_state={**gcp_credentials()},
    )
    resp = graphql_client.execute(
        GET_GOOGLE_CLOUD_SERVICES, variables={'id': connection_account.id}
    )
    services = resp['data']['getGoogleCloudServices']['services']
    assert services[0]['name'] == 'sqladmin.googleapis.com'
    assert len(services) == 1


def gcp_connection_account(**kwargs):
    return create_connection_account(
        GCP_VENDOR,
        authentication={},
        configuration_state={**gcp_credentials(), 'settings': {}},
        **kwargs
    )


def gcp_credentials():
    path = TEST_DIR / 'raw_wizard_state_credentials.json'
    file = open(path, 'r').read()
    return json.loads(file)


GET_GOOGLE_CLOUD_SERVICES = '''
    query getGoogleCloudServices($id: Int) {
    getGoogleCloudServices(connectionId: $id) {
      services {
        title
        name
        state
      }
    }
  }
    '''
