from collections import namedtuple
from unittest.mock import patch

import pytest

from integration import github
from integration.account import set_connection_account_number_of_records
from integration.exceptions import ConfigurationError
from integration.github.implementation import GITHUB_SYSTEM, N_RECORDS
from integration.github.tests.fake_api import (
    fake_github_api,
    fake_github_api_without_org,
)
from integration.models import PENDING, ConnectionAccount
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import get_db_number_of_records
from integration.views import oauth_callback
from objects.models import LaikaObject, LaikaObjectType
from objects.system_types import PULL_REQUEST
from organization.models import Organization


@pytest.fixture
def connection_account():
    with fake_github_api():
        yield github_connection_account()


def github_connection_account(organization: Organization = None):
    return create_connection_account(
        'GitHub',
        organization=organization,
        authentication=dict(
            access_token='MyToken', scope='repo read:org user user:email'
        ),
        configuration_state=dict(settings={'visibility': ["PUBLIC", "PRIVATE"]}),
    )


@pytest.fixture
def connection_account_validate_org():
    with fake_github_api_without_org():
        yield github_connection_account()


@pytest.mark.functional
def test_github_integration_create_laika_objects(connection_account):
    github.run(connection_account)
    pull_requests = LaikaObject.objects.filter(
        object_type__type_name=PULL_REQUEST.type,
        data__Organization='LaikaTest',
        data__Repository='laika-app',
    )
    assert pull_requests.count() == 5

    def get_approvers():
        pull_request_info = namedtuple('PullRequestInfo', 'approvers')
        for pr in pull_requests:
            yield pull_request_info(pr.data['Approvers'])

    approver_info = get_approvers()
    assert next(approver_info).approvers == 'ronaldzuniga'
    assert next(approver_info).approvers == ''
    assert next(approver_info).approvers == 'jeffrey,otto'
    assert next(approver_info).approvers == ''
    assert next(approver_info).approvers == 'jeffrey'


@pytest.mark.functional
def test_github_integrate_account_number_of_records(connection_account):
    github.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_github_integration_callback(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, GITHUB_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    expected_prefetch = _expected_custom_field_option()

    prefetch = connection_account.authentication['prefetch_organization']
    assert prefetch == expected_prefetch
    assert connection_account.status == PENDING
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=PULL_REQUEST.type
    )


@pytest.mark.functional
def test_github_integration_callback_with_missing_org(connection_account_validate_org):
    with pytest.raises(ConfigurationError):
        github.callback('code', 'github-test', connection_account_validate_org)


@pytest.mark.functional
def test_get_custom_field_options(connection_account):
    get_organization_options = github.get_custom_field_options(
        "organization", connection_account
    )
    expected_organizations = _expected_custom_field_option()
    first_id = get_organization_options.options[0]['id']
    first_name = get_organization_options.options[0]['value']['name']
    assert first_id == expected_organizations[0]['id']
    assert first_name == expected_organizations[0]['value']['name']

    second_id = get_organization_options.options[1]['id']
    second_name = get_organization_options.options[1]['value']['name']
    assert second_id == expected_organizations[1]['id']
    assert second_name == expected_organizations[1]['value']['name']


@pytest.mark.functional
def test_raise_error_for_unknown_field(connection_account):
    with pytest.raises(NotImplementedError):
        github.get_custom_field_options("project", connection_account)


@pytest.mark.functional
def test_github_integration_with_one_organization_settings(connection_account):
    settings = {'organizations': ['LaikaTest'], 'visibility': ['PRIVATE']}
    connection_account.configuration_state['settings'] = settings

    with patch('integration.github.http_client.read_all_pull_requests') as mock_http:
        github.run(connection_account)
        mock_http.assert_called_once()


@pytest.mark.functional
def test_github_integration_with_two_organization_settings(connection_account):
    settings = {
        'organizations': ['LaikaTest', 'LaikaTest-2'],
        'visibility': ['PRIVATE', 'PUBLIC'],
    }
    connection_account.configuration_state['settings'] = settings

    with patch('integration.github.http_client.read_all_pull_requests') as mock_http:
        github.run(connection_account)
        assert mock_http.call_count == 2


def _expected_custom_field_option():
    return [
        {'id': 'LaikaTest', 'value': {'name': 'Laika Test 1'}},
        {'id': 'LaikaTest-2', 'value': {'name': 'Laika Test 2'}},
    ]
