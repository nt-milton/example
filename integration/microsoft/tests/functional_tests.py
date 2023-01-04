import json

import pytest
from httmock import HTTMock, response, urlmatch

from integration import microsoft
from integration.account import set_connection_account_number_of_records
from integration.exceptions import ConfigurationError
from integration.integration_utils import microsoft_utils
from integration.integration_utils.microsoft_utils import PAGE_SIZE
from integration.microsoft import implementation
from integration.microsoft.implementation import MICROSOFT_SYSTEM, N_RECORDS
from integration.microsoft.tests.fake_api import (
    PARENT_PATH,
    fake_microsoft_api,
    fake_microsoft_api_with_error,
    resource_not_found_response,
)
from integration.models import PENDING, ConnectionAccount, OrganizationVendorUserSSO
from integration.settings import MICROSOFT_API_URL
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import get_db_number_of_records
from integration.views import oauth_callback
from objects.models import LaikaObject
from vendor.models import (
    DISCOVERY_STATUS_CONFIRMED,
    DISCOVERY_STATUS_NEW,
    OrganizationVendor,
    VendorCandidate,
)
from vendor.tests.factory import create_vendor

from .fake_api import users


@pytest.fixture
def connection_account(mock_renew_token):
    # Omit validation for testing purpose
    # because sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    with fake_microsoft_api():
        yield microsoft_connection_account()


@pytest.fixture
def connection_account_with_none_response():
    # Omit validation for testing purpose
    # because sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    with fake_microsoft_api_with_error():
        yield microsoft_connection_account()


@pytest.fixture
def connection_account_groups_validation(mock_renew_token):
    # Omit validation for testing purpose
    # because sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    with fake_microsoft_api():
        yield microsoft_group_connection_account()


@pytest.fixture
def sign_ins():
    raw_sign_ins_path = PARENT_PATH / 'raw_sign_ins_response.json'
    raw_sign_ins = open(raw_sign_ins_path, 'r').read()
    yield json.loads(raw_sign_ins)['value']


@pytest.mark.functional
def test_microsoft_denial_of_consent_validation(connection_account):
    with pytest.raises(ConfigurationError):
        microsoft.callback(None, 'redirect_uri', connection_account)


@pytest.mark.functional
def test_microsoft_callback_status(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, MICROSOFT_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    prefetch_options = connection_account.authentication['prefetch_group']
    assert prefetch_options == _expected_custom_options()
    assert connection_account.status == PENDING


@pytest.fixture
def failure_users_counting():
    return {'count': 0}


@pytest.mark.functional
def test_microsoft_integration_too_many_request(
    connection_account, failure_users_counting
):
    @urlmatch(netloc='graph.microsoft.com', path=r'/v1.0/groups/[A-Za-z0-9-]+/members')
    def users_too_many_requests(url, request):
        failure_users_counting['count'] = int(failure_users_counting['count']) + 1
        if int(failure_users_counting['count']) == 1:
            return response(
                status_code=429,
                headers={'Retry-After': 1},
                content='{"error": "too-many-requests"}',
            )
        return response(status_code=200, content=users())

    with HTTMock(users_too_many_requests):
        microsoft.run(connection_account)
    assert LaikaObject.objects.filter(connection_account=connection_account).exists()


@pytest.mark.functional
def test_microsoft_integration_resource_not_found(
    connection_account,
):
    @urlmatch(netloc='graph.microsoft.com')
    def resource_not_found(url, request):
        if 'memberOf' in url.path:
            return response(status_code=404, content=resource_not_found_response())

    with HTTMock(resource_not_found):
        microsoft.run(connection_account)
    assert LaikaObject.objects.filter(connection_account=connection_account).exists()


@pytest.mark.functional
def test_microsoft_integrate_account_number_of_records(connection_account):
    microsoft.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_microsoft_integration_get_custom_field_options(connection_account):
    expected_options = _expected_custom_options()
    groups = microsoft.get_custom_field_options('group', connection_account)

    assert groups.options == expected_options


@pytest.mark.functional
def test_raise_error_for_unknown_field(connection_account):
    with pytest.raises(NotImplementedError):
        microsoft.get_custom_field_options("repositories", connection_account)


@pytest.mark.functional
def test_integrate_vendor_candidates(connection_account, sign_ins):
    connection_account.authentication['scope'] = implementation.VENDOR_SCOPES
    microsoft.run(connection_account)
    assert VendorCandidate.objects.filter(
        organization=connection_account.organization
    ).count() == len(sign_ins)


@pytest.mark.functional
def test_integrate_vendor_candidates_with_valid_vendors(connection_account, sign_ins):
    connection_account.authentication['scope'] = implementation.VENDOR_SCOPES
    vendors = [create_vendor(name=sign_in['appDisplayName']) for sign_in in sign_ins]
    microsoft.run(connection_account)
    assert VendorCandidate.objects.filter(
        organization=connection_account.organization, status=DISCOVERY_STATUS_NEW
    ).count() == len(vendors)


@pytest.mark.skip()
@pytest.mark.functional
def test_integrate_vendor_pagination_none_response(
    connection_account_with_none_response,
):
    sign_ins = []
    with pytest.raises(ConfigurationError):
        audits_log_url = f'{MICROSOFT_API_URL}/auditLogs/signIns?$top={PAGE_SIZE}'
        response = microsoft_utils.graph_page_generator(
            'test-token',
            audits_log_url,
        )
        for sign_in in response:
            sign_ins.append(sign_in)


@pytest.mark.functional
def test_integrate_vendor_with_pagination(
    connection_account,
):
    sign_ins = []
    audits_log_url = f'{MICROSOFT_API_URL}/auditLogs/signIns?$top={PAGE_SIZE}'
    response = microsoft_utils.graph_page_generator(
        'test-token',
        audits_log_url,
    )
    for sign_in in response:
        sign_ins.append(sign_in)

    assert len(sign_ins) == 3


@pytest.mark.functional
def test_map_roles_groups_none_response():
    response = None
    values = microsoft_utils.map_groups_roles(response)
    assert values.__next__() == ([], [])


@pytest.mark.functional
def test_map_roles_groups_empty_response():
    response = {"value": []}
    values = microsoft_utils.map_groups_roles(response)
    assert values.__next__() == ([], [])


@pytest.mark.functional
def test_validate_groups(connection_account_groups_validation):
    implementation.run(connection_account_groups_validation)
    groups_settings = connection_account_groups_validation.configuration_state.get(
        'settings'
    )

    prefetch_groups = connection_account_groups_validation.authentication.get(
        'prefetch_group'
    )

    assert len(groups_settings.get('groups')) == 2
    assert len(prefetch_groups) == 3


@pytest.mark.functional
def test_integrate_vendor_candidates_with_existing_relations(
    connection_account, sign_ins
):
    connection_account.authentication['scope'] = implementation.VENDOR_SCOPES
    organization = connection_account.organization
    for sign_in in sign_ins:
        vendor = create_vendor(name=sign_in['appDisplayName'])
        OrganizationVendor.objects.create(organization=organization, vendor=vendor)
    microsoft.run(connection_account)
    assert (
        VendorCandidate.objects.filter(
            organization=connection_account.organization,
            status=DISCOVERY_STATUS_CONFIRMED,
        ).count()
        == 0
    )


@pytest.mark.functional
def test_integrate_sso_users(connection_account, sign_ins):
    connection_account.authentication['scope'] = implementation.VENDOR_SCOPES
    vendors = [create_vendor(name=sign_in['appDisplayName']) for sign_in in sign_ins]
    for vendor in vendors:
        OrganizationVendor.objects.create(
            organization=connection_account.organization, vendor=vendor
        )
    microsoft.run(connection_account)
    assert OrganizationVendorUserSSO.objects.filter(
        connection_account=connection_account
    ).count() == len(sign_ins)


@pytest.mark.functional
def test_integrate_sso_users_no_vendors(connection_account, sign_ins):
    connection_account.authentication['scope'] = implementation.VENDOR_SCOPES
    microsoft.run(connection_account)
    assert (
        OrganizationVendorUserSSO.objects.filter(
            connection_account=connection_account
        ).count()
        == 0
    )


def microsoft_connection_account(**kwargs):
    return create_connection_account(
        MICROSOFT_SYSTEM,
        authentication=dict(access_token="TEST_TOKEN", refresh_token="TEST_TOKEN"),
        configuration_state=dict(
            settings={
                'groups': [
                    '43243424-a0dc-42ec-9ce7-28b91d59563e',
                    '9f90c6bb-aaaf-4261-9091-bfb0171933c4',
                ]
            },
        ),
        **kwargs,
    )


def microsoft_group_connection_account(**kwargs):
    return create_connection_account(
        MICROSOFT_SYSTEM,
        authentication=dict(
            access_token="TEST_TOKEN",
            refresh_token="TEST_TOKEN",
            prefetch_group=[
                {
                    'id': '43243424-a0dc-42ec-9ce7-28b91d59563e',
                    'value': {'name': 'Test-group-1'},
                },
                {
                    'id': '9f90c6bb-aaaf-4261-9091-bfb0171933c4',
                    'value': {'name': 'Test-group-2'},
                },
                {
                    'id': 'ae42e96e-2a9f-4e4c-b9cb-ba5f410246a2',
                    'value': {'name': 'Test-group-3'},
                },
                {
                    'id': 'ae42e96e-2a9f-4e4c-b9cb-ba5f410246a245',
                    'value': {'name': 'Test-group-4'},
                },
            ],
        ),
        configuration_state=dict(
            settings={
                'groups': [
                    '43243424-a0dc-42ec-9ce7-28b91d59563e',
                    '9f90c6bb-aaaf-4261-9091-bfb0171933c4',
                    'ae42e96e-2a9f-4e4c-b9cb-ba5f410246a245',
                ]
            },
        ),
        **kwargs,
    )


def _expected_custom_options():
    return [
        {
            'id': '43243424-a0dc-42ec-9ce7-28b91d59563e',
            'value': {'name': 'Test-group-1'},
        },
        {
            'id': '9f90c6bb-aaaf-4261-9091-bfb0171933c4',
            'value': {'name': 'Test-group-2'},
        },
        {
            'id': 'ae42e96e-2a9f-4e4c-b9cb-ba5f410246a2',
            'value': {'name': 'Test-group-3'},
        },
    ]
