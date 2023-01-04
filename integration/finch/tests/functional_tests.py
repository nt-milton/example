import json
from unittest.mock import patch

import pytest
import requests.exceptions
from httmock import HTTMock
from httmock import response as mock_response
from httmock import urlmatch

from address.models import Address
from alert.models import Alert, PeopleDiscoveryAlert
from integration import error_codes, finch
from integration.account import set_connection_account_number_of_records
from integration.constants import SUCCESS
from integration.encryption_utils import encrypt_value
from integration.error_codes import EXPIRED_TOKEN, PROVIDER_SERVER_ERROR
from integration.exceptions import ConfigurationError, TimeoutException
from integration.factory import get_integration
from integration.finch.implementation import (
    _integrate_company,
    integrate_organization,
    load_employments,
    map_location,
    run,
)
from integration.finch.tests import fake_api
from integration.finch.tests.fake_api import (
    INDIVIDUAL_WITH_ONLY_PERSONAL_PHONE,
    ONLY_PERSONAL_EMAIL_INDIVIDUAL,
    TEST_INDIVIDUAL_WITHOUT_PHONES,
    fake_employments_response,
)
from integration.integration_utils.people_utils import SKIP_USERS, save_locations
from integration.models import ConnectionAccount
from integration.tests import create_connection_account
from integration.tests.factory import create_integration
from laika.settings import DJANGO_SETTINGS
from laika.tests import mock_responses
from organization.models import ONBOARDING, Organization, OrganizationLocation
from user.constants import ROLE_MEMBER, ROLE_SUPER_ADMIN
from user.models import (
    DISCOVERY_STATE_CONFIRMED,
    DISCOVERY_STATE_NEW,
    EMPLOYMENT_STATUS_ACTIVE,
    EMPLOYMENT_STATUS_INACTIVE,
    User,
)
from user.tests import create_user
from user.utils.invite_partial_user import invite_partial_user_m

ENGINEER_EMAIL = 'danny@heylaika.com'
MANAGER_EMAIL = 'ronald@heylaika.com'
LEAD_EMAIL = 'otto@heylaika.com'
PRODUCT_EMAIL = 'taj@heylaika.com'
ENGINEER_FINCH_UUID = '7045b408-2043-4d57-91b5-87b11b22baae'
ENGINEER_UPDATED_EMAIL = 'carlos@heylaika.com'

AWS_COGNITO = 'laika.aws.cognito.cognito'


@pytest.mark.functional
def test_finch_factory(connection_account):
    integration = get_integration(connection_account)
    assert integration


@pytest.mark.functional
def test_locations(connection_account):
    integrate_organization('', connection_account)

    address = Address.objects.first()
    location = OrganizationLocation.objects.first()
    assert str(address) == '335 S 560 W - (Lindon, UT, US, 84042)'
    assert location.name == 'Location-1'
    assert location.hq


@pytest.mark.functional
def test_multiple_locations_only_one_hq(connection_account):
    address = Address.objects.create(street1='headquarters nyc')
    OrganizationLocation.objects.create(
        organization=connection_account.organization, address=address, hq=True
    )

    integrate_organization('', connection_account)
    hq = OrganizationLocation.objects.get(
        organization=connection_account.organization, hq=True
    )
    assert OrganizationLocation.objects.count() == 3
    assert hq.name == 'Location-1'


@pytest.mark.functional
def test_save_locations_keep_hq_changes(connection_account):
    locations = [fake_api.TEST_LOCATION, {'line1': 'ca street 1', 'line2': ''}]
    save_locations(locations, connection_account.organization, map_location)
    OrganizationLocation.objects.filter(name='Location-2').update(hq=True)

    save_locations(locations, connection_account.organization, map_location)

    hq = OrganizationLocation.objects.get(
        organization=connection_account.organization, hq=True
    )
    assert hq.name == 'Location-2'


@pytest.mark.functional
def test_people(connection_account, create_permission_groups):
    _integrate_company(connection_account)

    assert User.objects.filter(email=ENGINEER_EMAIL).exists()
    assert User.objects.filter(email=MANAGER_EMAIL).exists()
    # User doesn't have emails in the response.
    assert not User.objects.filter(email=LEAD_EMAIL).exists()
    assert not User.objects.filter(email=PRODUCT_EMAIL).exists()

    # User doesn't have a WORK email in the response.
    personal_email_finch_uuid = ONLY_PERSONAL_EMAIL_INDIVIDUAL.get('id')
    assert not User.objects.filter(finch_uuid=personal_email_finch_uuid).exists()

    personal_phone_finch_uuid = INDIVIDUAL_WITH_ONLY_PERSONAL_PHONE.get('id')
    assert User.objects.filter(finch_uuid=personal_phone_finch_uuid).exists()
    phone_user = User.objects.get(finch_uuid=personal_phone_finch_uuid)
    assert phone_user.phone_number is None

    no_phones_finch_uuid = TEST_INDIVIDUAL_WITHOUT_PHONES.get('id')
    assert User.objects.filter(finch_uuid=no_phones_finch_uuid).exists()
    no_phone_user = User.objects.get(finch_uuid=no_phones_finch_uuid)
    assert no_phone_user.phone_number is None


@pytest.mark.functional
def test_people_discovery_onboarding_confirmed(
    connection_account, create_permission_groups
):
    connection_account.organization.state = ONBOARDING
    _integrate_company(connection_account)

    assert (
        User.objects.get(email=ENGINEER_EMAIL).discovery_state
        == DISCOVERY_STATE_CONFIRMED
    )
    assert (
        User.objects.get(email=MANAGER_EMAIL).discovery_state
        == DISCOVERY_STATE_CONFIRMED
    )


@pytest.mark.functional
def test_people_manager(connection_account, create_permission_groups):
    _integrate_company(connection_account)
    manager = User.objects.filter(email=MANAGER_EMAIL).first()
    engineer = User.objects.filter(email=ENGINEER_EMAIL).first()
    assert manager.id == engineer.manager.id
    assert manager.manager is None
    assert manager.connection_account == connection_account


@pytest.mark.functional
def test_people_not_active_by_default(connection_account, create_permission_groups):
    _integrate_company(connection_account)

    assert User.objects.filter(email=ENGINEER_EMAIL, is_active=False).exists()


@pytest.mark.functional
def test_existing_people_is_not_discovered(
    connection_account, create_permission_groups
):
    User.objects.create(
        email=ENGINEER_EMAIL,
        organization=connection_account.organization,
        discovery_state=DISCOVERY_STATE_CONFIRMED,
    )
    _integrate_company(connection_account)

    assert User.objects.filter(
        email=ENGINEER_EMAIL, discovery_state=DISCOVERY_STATE_CONFIRMED
    ).exists()


@pytest.mark.functional
def test_new_people_is_discovered(connection_account, create_permission_groups):
    _integrate_company(connection_account)

    assert User.objects.filter(
        email=ENGINEER_EMAIL, discovery_state=DISCOVERY_STATE_NEW
    ).exists()


@pytest.mark.functional
def test_multiple_runs_keeps_discovery_state(
    connection_account, create_permission_groups
):
    _integrate_company(connection_account)

    _integrate_company(connection_account)

    assert User.objects.filter(
        email=ENGINEER_EMAIL, discovery_state=DISCOVERY_STATE_NEW
    ).exists()


@pytest.mark.functional
def test_people_keep_active(connection_account, create_permission_groups):
    create_user(connection_account.organization, email=ENGINEER_EMAIL, is_active=True)

    _integrate_company(connection_account)

    assert User.objects.filter(email=ENGINEER_EMAIL, is_active=True).exists()


@pytest.mark.functional
def test_disable_missing_people(connection_account, create_permission_groups):
    user_input = dict(
        organization_id=connection_account.organization.id,
        first_name='Missing',
        last_name='User',
        email='test1@heylaika.com',
        employment_status=EMPLOYMENT_STATUS_ACTIVE,
    )
    invite_partial_user_m(
        connection_account.organization, user_input, connection_id=connection_account.id
    )
    _integrate_company(connection_account)

    assert User.objects.filter(employment_status=EMPLOYMENT_STATUS_ACTIVE).count() == 5
    assert User.objects.filter(employment_status=EMPLOYMENT_STATUS_INACTIVE).exists()


@pytest.mark.functional
def test_disable_user(connection_account, create_permission_groups):
    email = 'test2@heylaika.com'
    create_user(
        connection_account.organization,
        email=email,
        is_active=True,
        employment_status=EMPLOYMENT_STATUS_ACTIVE,
        connection_account=connection_account,
    )

    with patch(AWS_COGNITO) as cognito:
        _integrate_company(connection_account)

        assert User.objects.filter(
            email=email, employment_status=EMPLOYMENT_STATUS_INACTIVE
        ).exists()
        # OP-364: Expect cognito to NOT being called.
        # cognito.admin_disable_user.assert_called_with(
        #     UserPoolId=DJANGO_SETTINGS.get('LEGACY_POOL_ID'),
        #     Username=email
        # )
        cognito.admin_disable_user.assert_not_called()


@pytest.mark.functional
def test_enable_user(connection_account, create_permission_groups):
    email = 'danny@heylaika.com'
    create_user(
        connection_account.organization,
        email=email,
        is_active=False,
        employment_status=EMPLOYMENT_STATUS_INACTIVE,
        connection_account=connection_account,
        username=email,
    )

    with patch(AWS_COGNITO) as cognito:
        _integrate_company(connection_account)

        assert User.objects.filter(
            email=email, is_active=True, employment_status='active'
        ).exists()
        cognito.admin_enable_user.assert_called_with(
            UserPoolId=DJANGO_SETTINGS.get('LEGACY_POOL_ID'), Username=email
        )


@pytest.mark.functional
def test_expired_connection(expired_connection_account):
    with pytest.raises(ConfigurationError):
        with expired_connection_account.connection_attempt():
            _integrate_company(expired_connection_account)

    assert expired_connection_account.error_code == EXPIRED_TOKEN


@pytest.mark.functional
def test_vendor_server_error_connection(internal_error_connection_account):
    with pytest.raises(ConfigurationError):
        with internal_error_connection_account.connection_attempt():
            _integrate_company(internal_error_connection_account)

    assert internal_error_connection_account.error_code == PROVIDER_SERVER_ERROR


@pytest.mark.functional
def test_organization_name(connection_account):
    with fake_api.fake_finch_api():
        integrate_organization('DummyToken', connection_account)

    updated_org = Organization.objects.first()
    assert updated_org.name == fake_api.TEST_COMPANY
    assert updated_org.legal_name == fake_api.TEST_COMPANY


@pytest.fixture
def expired_connection_account():
    error_content = json.dumps(
        {'finch_code': 'account_setup_required', 'message': 'account expired'}
    )
    error = mock_response(status_code=401, content=error_content, reason='')
    with mock_responses([error]):
        yield create_finch_connection()


@pytest.fixture
def internal_error_connection_account():
    error_content = json.dumps(
        {
            'statusCode': '500',
            'status': '500',
            'code': '500',
            'message': 'Internal Server Error',
            'name': 'server_error',
        }
    )
    error = mock_response(status_code=500, content=error_content)
    with mock_responses([error]):
        yield create_finch_connection()


@pytest.fixture
def connection_account():
    with fake_api.fake_finch_api():
        yield create_finch_connection()


@pytest.fixture
def connection_account_with_filter_domains():
    with fake_api.fake_finch_api():
        yield create_finch_connection_with_domains()


@pytest.fixture
def connection_account_without_employment_type():
    with fake_api.fake_finch_api_without_employment_type():
        yield create_finch_connection()


@pytest.fixture
def connection_account_for_connect_failure():
    with fake_api.fake_failed_finch_api():
        yield create_finch_connection_connect()


def create_finch_connection():
    integration = create_integration(
        vendor_name='BambooHR', metadata={'finchProvider': 'bamboo_hr'}
    )
    return create_connection_account(
        'Finch',
        integration=integration,
        authentication={
            "access_token": encrypt_value("18b2f0c0-c92f-4e1d-8e31-cf9b464ce25f")
        },
    )


def create_finch_connection_with_domains():
    integration = create_integration(
        vendor_name='BambooHR', metadata={'finchProvider': 'bamboo_hr'}
    )
    return create_connection_account(
        'Finch',
        integration=integration,
        authentication={
            "access_token": encrypt_value("18b2f0c0-c92f-4e1d-8e31-cf9b464ce25f")
        },
        configuration_state={'validDomains': ['heylaika.com']},
    )


def create_finch_connection_connect():
    integration = create_integration(
        vendor_name='BambooHR', metadata={'finchProvider': 'bamboo_hr'}
    )
    return create_connection_account(
        'Finch',
        integration=integration,
        configuration_state={"credentials": "6bf87fd3-3628-4a10-9d79-e47b22f4194e"},
    )


@pytest.mark.functional
def test_people_discovery_alert(connection_account, create_permission_groups):
    create_user(
        connection_account.organization,
        email='test3@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='test',
        discovery_state=DISCOVERY_STATE_NEW,
    )
    create_user(
        connection_account.organization,
        email='test-2@heylaika.com',
        role=ROLE_MEMBER,
        first_name='test-2',
        discovery_state=DISCOVERY_STATE_NEW,
    )
    finch.run(connection_account)
    alerts_count = Alert.objects.count()
    people_discovery_alerts = PeopleDiscoveryAlert.objects.count()
    connection_account = ConnectionAccount.objects.get(id=connection_account.id)

    assert (
        connection_account.discovered_people_amount
        == connection_account.result['People_discovered']
    )
    assert connection_account.people_amount == connection_account.result['People']
    assert people_discovery_alerts == 2
    assert alerts_count == 2


@pytest.mark.functional
def test_finch_integrate_account_number_of_records(
    connection_account, create_permission_groups
):
    finch.run(connection_account)
    result = {"People": 500}
    expected = str(set_connection_account_number_of_records(connection_account, result))
    assert str(result) == expected


@pytest.mark.functional
def test_finch_without_employment_type(
    connection_account_without_employment_type, create_permission_groups
):
    finch.run(connection_account_without_employment_type)
    assert connection_account_without_employment_type.status == SUCCESS


@pytest.mark.functional
def test_populate_finch_uuid_on_existing_email(
    connection_account, create_permission_groups
):
    create_user(connection_account.organization, email=ENGINEER_EMAIL, is_active=True)

    _integrate_company(connection_account)

    assert User.objects.get(email=ENGINEER_EMAIL).finch_uuid


@pytest.mark.functional
def test_do_not_update_existing_email(connection_account, create_permission_groups):
    create_user(
        connection_account.organization,
        email=ENGINEER_UPDATED_EMAIL,
        finch_uuid=ENGINEER_FINCH_UUID,
        is_active=True,
    )

    _integrate_company(connection_account)
    assert (
        User.objects.get(finch_uuid=ENGINEER_FINCH_UUID).email == ENGINEER_UPDATED_EMAIL
    )


@pytest.mark.functional
def test_duplicate_finch_id_integration_has_priority(
    connection_account, create_permission_groups
):
    # OP-364: Remove the disable user. Read the ticket comments for more
    # context
    # pool_id = DJANGO_SETTINGS.get('LEGACY_POOL_ID')

    def create_duplicate(email):
        create_user(
            connection_account.organization,
            email=email,
            finch_uuid=ENGINEER_FINCH_UUID,
            employment_status=EMPLOYMENT_STATUS_ACTIVE,
            connection_account=connection_account,
            is_active=True,
        )

    create_duplicate('personal@gmail.com')
    create_duplicate(ENGINEER_EMAIL)
    create_duplicate('personal3@gmail.com')

    def validate_activation(*args):
        person, *_ = args
        assert person['email'].endswith('@heylaika.com')

    with patch(
        'integration.integration_utils.people_utils.require_activation',
        side_effect=validate_activation,
    ), patch(AWS_COGNITO) as cognito:
        _integrate_company(connection_account)
        # OP-364: Expect cognito to NOT being called.
        # expected_calls = [
        #     call(UserPoolId=pool_id, Username='personal@gmail.com'),
        #     call(UserPoolId=pool_id, Username='personal3@gmail.com')
        # ]
        # cognito.admin_disable_user.assert_has_calls(
        #     expected_calls
        # )
        cognito.admin_disable_user.assert_not_called()

    assert (
        User.objects.filter(
            email__endswith='@gmail.com', employment_status=EMPLOYMENT_STATUS_INACTIVE
        ).count()
        == 2
    )


@pytest.mark.functional
def test_create_user_with_finch_uuid(connection_account, create_permission_groups):
    _integrate_company(connection_account)
    assert User.objects.get(finch_uuid=ENGINEER_FINCH_UUID).email is not None


@pytest.fixture
def function_call_counting():
    return {'count': 0}


@pytest.mark.functional
def test_finch_timeout_exception_error_result(
    connection_account, function_call_counting
):
    @urlmatch(netloc=r'api.tryfinch.com', path='/employer/directory')
    def call_employer_directory(url, request):
        function_call_counting['count'] = int(function_call_counting['count']) + 1
        return mock_response(status_code=408, content=' {"error": "timeout error"}')

    with HTTMock(call_employer_directory):
        with pytest.raises(TimeoutException):
            run(connection_account)

    assert connection_account.result.get('error_response') == 'Timeout Error.'
    assert connection_account.status == 'error'
    assert function_call_counting.get('count') == 3
    assert connection_account.error_code == error_codes.CONNECTION_TIMEOUT


@pytest.mark.functional
def test_dont_add_integrations_skip_users(connection_account, create_permission_groups):
    _integrate_company(connection_account)
    assert not User.objects.filter(email__in=SKIP_USERS).exists()


@pytest.mark.functional
def test_company_not_available(connection_account):
    @urlmatch(netloc=r'api.tryfinch.com', path='/employer/company')
    def call_company(url, request):
        return mock_response(
            status_code=501,
            content=(
                '{"message": '
                '"Company endpoint is not '
                'available for API tokens",'
                ' "name":"not_implemented_error"} '
            ),
        )

    with HTTMock(call_company):
        integrate_organization('', connection_account)

    assert connection_account.status != 'error'


@pytest.mark.functional
def test_employment_read_timeout(
    connection_account, function_call_counting, create_permission_groups
):
    @urlmatch(netloc=r'api.tryfinch.com', path='/employer/employment')
    def call_employment(url, request):
        function_call_counting['count'] = int(function_call_counting['count']) + 1
        if int(function_call_counting['count']) == 1:
            raise requests.exceptions.ReadTimeout

    with HTTMock(call_employment):
        run(connection_account)

    assert connection_account.status == 'success'
    assert int(function_call_counting['count']) == 2


@pytest.mark.functional
def test_should_alert_when_income_data(
    connection_account, create_permission_groups, caplog
):
    mock_token = "ABC"

    @urlmatch(netloc=r'api.tryfinch.com', path='/employer/employment')
    def call_employment(url, request):
        return fake_employments_response()

    with HTTMock(call_employment):
        load_employments(access_token=mock_token, ids=["1", "2", "3"])
    assert '🔥 INCOME object is present on Finch response' in caplog.text


@pytest.mark.functional
def test_company_fails(connection_account_for_connect_failure):
    with pytest.raises(ConfigurationError):
        finch.connect(connection_account_for_connect_failure)

    assert (
        connection_account_for_connect_failure.error_code
        == error_codes.PROVIDER_SERVER_ERROR
    )


@pytest.mark.functional
def test_new_people_is_discovered_with_domain_email(
    connection_account_with_filter_domains, create_permission_groups
):
    _integrate_company(connection_account_with_filter_domains)

    assert User.objects.filter(
        email=ENGINEER_EMAIL, discovery_state=DISCOVERY_STATE_NEW
    ).exists()
    assert not User.objects.filter(
        email='integrations@pave.com', discovery_state=DISCOVERY_STATE_NEW
    ).exists()
