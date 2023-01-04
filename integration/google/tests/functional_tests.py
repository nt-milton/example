import json

import pytest
from httmock import HTTMock, response, urlmatch

from alert.models import Alert
from integration import google
from integration.account import set_connection_account_number_of_records
from integration.exceptions import ConfigurationError
from integration.google.implementation import (
    DEFAULT_ORG_UNIT,
    GOOGLE_WORKSPACE_SYSTEM,
    N_RECORDS,
    ROLE_SCOPE,
    VENDOR_SCOPES,
)
from integration.google.tests.fake_api import (
    TEST_DIR,
    fake_google_tokens_access_api,
    fake_google_workspace_api,
    fake_google_workspace_api_forbidden,
    fake_google_workspace_api_without_permissions,
    fake_users,
)
from integration.models import (
    ERROR,
    PENDING,
    ConnectionAccount,
    OrganizationVendorUserSSO,
)
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import get_db_number_of_records
from integration.views import oauth_callback
from objects.models import LaikaObject, LaikaObjectType
from objects.system_types import ACCOUNT, USER
from user.constants import ROLE_MEMBER, ROLE_SUPER_ADMIN
from user.tests import create_user
from vendor.models import (
    DISCOVERY_STATUS_CONFIRMED,
    DISCOVERY_STATUS_NEW,
    OrganizationVendor,
    Vendor,
    VendorCandidate,
    VendorDiscoveryAlert,
)
from vendor.tests.factory import create_vendor


@pytest.fixture
def connection_account():
    with fake_google_workspace_api():
        yield google_workspace_connection_account()


@pytest.fixture
def connection_account_access_tokens():
    with fake_google_tokens_access_api():
        yield google_workspace_connection_account()


@pytest.fixture
def connection_account_without_permissions():
    with fake_google_workspace_api_without_permissions():
        yield google_workspace_connection_account()


@pytest.fixture
def connection_account_with_forbidden():
    with fake_google_workspace_api_forbidden():
        yield google_workspace_connection_account()


@pytest.fixture
def tokens():
    raw_tokens_path = TEST_DIR / 'raw_tokens_response.json'
    raw_tokens = open(raw_tokens_path, 'r').read()
    yield json.loads(raw_tokens)['items']


@pytest.fixture
def users():
    raw_users_path = TEST_DIR / 'raw_users_response.json'
    raw_users = open(raw_users_path, 'r').read()
    yield json.loads(raw_users)['users']


@pytest.mark.functional
def test_google_workspace_integration_create_laika_objects(connection_account):
    google.run(connection_account)
    assert LaikaObject.objects.filter(object_type__type_name=USER.type).exists()
    assert LaikaObject.objects.filter(object_type__type_name=USER.type).count() == 4


@pytest.mark.functional
def test_google_workspace_integrate_users_with_settings(connection_account):
    settings = {'orgUnitPath': '/test'}
    connection_account.configuration_state['settings'] = settings
    google.run(connection_account)
    assert not LaikaObject.objects.filter(object_type__type_name=USER.type).exists()


@pytest.mark.functional
def test_google_workspace_integration_callback(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, GOOGLE_WORKSPACE_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    assert connection_account.status == PENDING
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=USER.type
    )
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=ACCOUNT.type
    )


@pytest.mark.functional
def test_config_error_for_google_workspace_without_permissions(
    connection_account_without_permissions,
):
    with pytest.raises(ConfigurationError):
        google.run(connection_account_without_permissions)


@pytest.mark.functional
def test_integrate_vendor_candidates(connection_account, tokens):
    connection_account.authentication['scope'] = VENDOR_SCOPES
    google.run(connection_account)
    new_vendor_candidates = VendorCandidate.objects.filter(
        organization=connection_account.organization
    ).count()
    assert new_vendor_candidates == len(tokens)


@pytest.mark.functional
def test_google_integrate_account_number_of_records(connection_account):
    google.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_integrate_vendor_candidates_with_existing_relations(
    connection_account, tokens
):
    connection_account.authentication['scope'] = VENDOR_SCOPES
    organization = connection_account.organization
    for token in tokens:
        vendor = create_vendor(name=token['displayText'])
        OrganizationVendor.objects.create(organization=organization, vendor=vendor)
    google.run(connection_account)
    assert (
        VendorCandidate.objects.filter(
            organization=connection_account.organization,
            status=DISCOVERY_STATUS_CONFIRMED,
        ).count()
        == 0
    )


@pytest.mark.functional
def test_integrate_vendor_candidates_with_valid_vendors(connection_account, tokens):
    connection_account.authentication['scope'] = VENDOR_SCOPES
    vendors = [create_vendor(name=token['displayText']) for token in tokens]
    google.run(connection_account)
    assert VendorCandidate.objects.filter(
        organization=connection_account.organization, status=DISCOVERY_STATUS_NEW
    ).count() == len(vendors)


@pytest.mark.functional
def test_integrate_sso_users(connection_account, tokens, users):
    connection_account.authentication['scope'] = VENDOR_SCOPES
    vendors = [create_vendor(name=token.get('displayText', '')) for token in tokens]
    for vendor in vendors:
        OrganizationVendor.objects.create(
            organization=connection_account.organization, vendor=vendor
        )
    google.run(connection_account)
    assert OrganizationVendorUserSSO.objects.filter(
        connection_account=connection_account
    ).exists()
    assert OrganizationVendorUserSSO.objects.filter(
        connection_account=connection_account
    ).count() == (len(users) * len(tokens))


@pytest.mark.functional
def test_integrate_sso_users_non_vendors(connection_account, tokens):
    connection_account.authentication['scope'] = VENDOR_SCOPES
    google.run(connection_account)
    assert not OrganizationVendorUserSSO.objects.filter(
        connection_account=connection_account
    ).exists()


@pytest.mark.functional
def test_google_workspace_integration_get_custom_field_options(connection_account):
    units_expected = [
        DEFAULT_ORG_UNIT,
        {'id': '/corp/sales', 'value': {'name': 'sales'}},
    ]
    units_options = google.get_custom_field_options('organization', connection_account)
    assert units_options.options[:2] == units_expected


@pytest.mark.functional
def test_google_workspace_integration_get_organizations_options(connection_account):
    units_expected = [
        DEFAULT_ORG_UNIT,
        {'id': '/corp/sales', 'value': {'name': 'sales'}},
    ]
    organizations_response = google.get_google_organizations(connection_account)
    assert organizations_response.options[:2] == units_expected


@pytest.mark.functional
def test_google_workspace_integration_get_custom_field_options_err(connection_account):
    with pytest.raises(NotImplementedError):
        google.get_custom_field_options('project', connection_account)


def google_workspace_connection_account(**kwargs):
    return create_connection_account(
        'Google Workspace',
        authentication=dict(refresh_token='MyToken', scope=ROLE_SCOPE),
        **kwargs
    )


@pytest.mark.functional
def test_callback_pending_after_error(connection_account):
    connection_account.status = ERROR
    connection_account.save()
    request = create_request_for_callback(connection_account)
    oauth_callback(request, GOOGLE_WORKSPACE_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    assert connection_account.status == PENDING


@pytest.mark.functional
def test_vendor_candidates_alert(connection_account, tokens, graphql_organization):
    connection_account.organization = graphql_organization
    create_user(
        graphql_organization,
        email='test@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='test',
    )
    create_user(
        graphql_organization,
        email='test-2@heylaika.com',
        role=ROLE_MEMBER,
        first_name='test-2',
    )
    connection_account.authentication['scope'] = VENDOR_SCOPES
    vendors = [create_vendor(name=token['displayText']) for token in tokens]
    google.run(connection_account)
    alerts_count = Alert.objects.count()
    vendor_alerts = VendorDiscoveryAlert.objects.count()
    vendor_alert = VendorDiscoveryAlert.objects.first()
    assert alerts_count == 2
    assert vendor_alerts == 2
    assert vendor_alert.quantity == len(vendors)


@pytest.mark.functional
def test_not_access_sso_tokens(
    connection_account_access_tokens,
):
    LAIKA_STAGING = 'Laika Staging'
    LAIKA = 'Laika'
    ASANA = 'Asana'
    GOOGLE_CHROME = 'Google Chrome'
    org = connection_account_access_tokens.organization
    connection_account_access_tokens.authentication['scope'] = VENDOR_SCOPES
    Vendor.objects.bulk_create(
        [
            Vendor(name=LAIKA_STAGING),
            Vendor(name=LAIKA),
            Vendor(name=ASANA),
            Vendor(name=GOOGLE_CHROME),
        ]
    )
    OrganizationVendor.objects.bulk_create(
        [
            OrganizationVendor(
                organization=org, vendor=Vendor.objects.get(name=LAIKA_STAGING)
            ),
            OrganizationVendor(organization=org, vendor=Vendor.objects.get(name=LAIKA)),
            OrganizationVendor(organization=org, vendor=Vendor.objects.get(name=ASANA)),
            OrganizationVendor(
                organization=org, vendor=Vendor.objects.get(name=GOOGLE_CHROME)
            ),
        ]
    )

    @urlmatch(netloc='www.googleapis.com')
    def users_too_many_requests(url, request):
        json_response = json.loads(fake_users())
        del json_response['nextPageToken']
        if 'customer=my_customer' in url.query:
            return response(status_code=200, content=json.dumps(json_response))

    with HTTMock(users_too_many_requests):
        google.run(connection_account_access_tokens)
    sso_user_emails = OrganizationVendorUserSSO.objects.filter(
        connection_account=connection_account_access_tokens
    ).values('email')
    emails = set()
    for sso_user_email in sso_user_emails:
        emails.add(sso_user_email.get('email'))
    assert len(emails) == 3
    # user with id '115602337442250165067' return 401 on get tokens
    assert 'tomas@heylaika.com' not in emails


@pytest.mark.functional
def test_config_error_for_google_workspace_with_forbidden_api(
    connection_account_with_forbidden,
):
    error_expected = {'message': 'Admin API not enabled', 'code': '403'}
    error_response = google.get_google_organizations(connection_account_with_forbidden)
    assert error_response.error == error_expected
