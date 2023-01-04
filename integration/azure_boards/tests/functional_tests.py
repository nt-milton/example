from unittest.mock import patch

import pytest

from integration.azure_boards import implementation
from integration.azure_boards.constants import AZURE_BOARDS_SYSTEM
from integration.azure_devops.tests.fake_api import fake_azure_devops_api
from integration.constants import PENDING, SUCCESS
from integration.models import ConnectionAccount
from integration.tests import create_connection_account, create_request_for_callback
from integration.views import oauth_callback
from objects.models import LaikaObject


@pytest.fixture
def fake_azure_api():
    with fake_azure_devops_api():
        yield


@pytest.fixture
def _expected_custom_organization():
    return {
        "id": "Laika-compliance-test",
        "value": {"name": "Laika-compliance-test"},
    }


@pytest.fixture
def _expected_custom_project():
    return {
        'id': 'Laika-compliance-test',
        'value': [
            {
                'id': 'ed78cbc0-5899-4831-9062-2a2f05010d07',
                'value': {'name': 'Compliance'},
            }
        ],
    }


@pytest.mark.functional
def test_azure_boards_callback_status(
    fake_azure_api, _expected_custom_organization, _expected_custom_project
):
    connection_account = azure_boards_connection_account()
    request = create_request_for_callback(connection_account)
    oauth_callback(request, AZURE_BOARDS_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    prefetch_options = connection_account.authentication['prefetch_organizations']
    prefetch_projects = connection_account.authentication['prefetch_projects']
    assert prefetch_options == [_expected_custom_organization]
    assert prefetch_projects == [_expected_custom_project]
    assert connection_account.status == PENDING


@pytest.mark.functional
def test_azure_boards_success_status(fake_azure_api):
    connection_account = azure_boards_connection_account()
    implementation.run(connection_account)
    assert connection_account.status == SUCCESS


@pytest.mark.functional
@pytest.mark.parametrize(
    'with_history',
    [True, False],
)
def test_azure_boards_success_status_with_laika_objects(with_history, fake_azure_api):
    connection_account = azure_boards_connection_account(with_history)
    implementation.run(connection_account)
    history = LaikaObject.objects.first().data.get('Transitions History')
    assert connection_account.status == SUCCESS
    assert bool(history) == with_history
    assert (
        LaikaObject.objects.filter(connection_account=connection_account).count() == 2
    )


@pytest.mark.functional
@patch('integration.azure_devops.rest_client.get_projects')
def test_azure_boards_read_all_projects(get_projects):
    get_projects.return_value = [{'name': 'testing 1'}, {'name': 'testing 2'}]
    got = implementation._read_all_projects('testing_token', 'testing_org')
    assert got == ['testing 1', 'testing 2']


def azure_boards_connection_account(with_history: bool = False):
    return create_connection_account(
        AZURE_BOARDS_SYSTEM,
        integration_metadata={
            'configuration_fields': ['test_field'],
            'param_redirect_uri': 'https://redirect.uri.com',
            'read_history': with_history,
        },
        authentication=dict(access_token='TEST_TOKEN', refresh_token='TEST_TOKEN'),
        configuration_state=dict(
            settings={
                'organization': 'test-org',
                'projects': ['Testing Boards'],
            },
        ),
    )
