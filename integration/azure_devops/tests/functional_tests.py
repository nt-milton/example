import pytest

from integration.azure_devops import implementation
from integration.azure_devops.constants import AZURE_DEVOPS_SYSTEM
from integration.azure_devops.tests.fake_api import fake_azure_devops_api
from integration.constants import PENDING, SUCCESS
from integration.models import ConnectionAccount
from integration.tests import create_connection_account, create_request_for_callback
from integration.views import oauth_callback
from objects.models import LaikaObject


@pytest.fixture
def connection_account():
    with fake_azure_devops_api():
        yield azure_devops_connection_account()


@pytest.fixture
def _expected_custom_options():
    return {
        "id": "Laika-compliance-test",
        "value": {"name": "Laika-compliance-test"},
    }


@pytest.mark.functional
def test_azure_devops_callback_status(connection_account, _expected_custom_options):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, AZURE_DEVOPS_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    prefetch_options = connection_account.authentication['prefetch_organization']
    assert prefetch_options == [_expected_custom_options]
    assert connection_account.status == PENDING


@pytest.mark.functional
def test_azure_devops_success_status(connection_account):
    implementation.run(connection_account)
    assert connection_account.status == SUCCESS


@pytest.mark.functional
def test_azure_devops_success_status_with_laika_objects(connection_account):
    implementation.run(connection_account)
    assert connection_account.status == SUCCESS
    assert LaikaObject.objects.filter(connection_account=connection_account).exists()


def azure_devops_connection_account():
    return create_connection_account(
        AZURE_DEVOPS_SYSTEM,
        authentication=dict(access_token="TEST_TOKEN", refresh_token="TEST_TOKEN"),
        configuration_state=dict(
            settings={'organization': 'test-org'},
        ),
    )
