import pytest

from integration.models import ConnectionAccount, IntegrationVersion
from integration.tests.factory import create_connection_account, create_integration
from integration.tests.functional_tests import GET_START_INTEGRATION_QUERY

TEST_VENDOR = 'TestVendor'


@pytest.fixture()
def mock_integration():
    return create_integration('TestVendor')


@pytest.fixture()
def initial_version(mock_integration):
    return IntegrationVersion.objects.create(
        version_number='0.0.1', description='Test version', integration=mock_integration
    )


@pytest.fixture
def connection_account(mock_integration):
    connection_account = create_connection_account(
        vendor_name=TEST_VENDOR, alias='Connection 1', integration=mock_integration
    )
    return connection_account


@pytest.mark.functional()
def test_integration_version_str(initial_version):
    expected = '0.0.1 TestVendor Integration Version'
    actual = initial_version.__str__()
    assert expected == actual


@pytest.mark.functional()
def test_connection_account_version(initial_version, connection_account):
    connection_account.integration_version = initial_version
    connection_account.save()
    assert (
        connection_account.integration_version.version_number
        == initial_version.version_number
    )


@pytest.mark.functional()
def test_integration_initial_version(mock_integration):
    integration_version = mock_integration.get_latest_version()
    assert integration_version.version_number == '1.0.0'


@pytest.mark.functional(permissions=['integration.add_connectionaccount'])
def test_create_integration_with_latest_version(graphql_client):
    vendor_name = TEST_VENDOR
    alias = 'test connection'
    create_integration(vendor_name)
    params = {'vendorName': vendor_name, 'alias': alias, 'subscriptionType': ''}

    response = graphql_client.execute(GET_START_INTEGRATION_QUERY, variables=params)[
        'data'
    ]['startIntegration']['connectionAccount']

    control = response['control']
    connection_account = ConnectionAccount.objects.filter(control=control)
    assert connection_account.exists()
    connection = connection_account.first()
    integration = connection.integration
    assert connection.integration_version == integration.get_latest_version()
