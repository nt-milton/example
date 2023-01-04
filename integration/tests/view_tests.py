import json

import pytest
from django.test import RequestFactory

from alert.constants import ALERT_TYPES
from alert.models import Alert
from conftest import JSON_CONTENT_TYPE
from integration.checkr.constants import NEEDS_REVIEW_STATUS
from integration.encryption_utils import encrypt_value
from integration.models import ConnectionAccount
from integration.tests import create_connection_account
from integration.views import laika_web_redirect, webhook_checkr
from laika.settings import DJANGO_SETTINGS
from objects.models import LaikaObject
from objects.system_types import BACKGROUND_CHECK, resolve_laika_object_type
from user.constants import ACTIVE, ONBOARDING, ROLE_ADMIN
from user.models import BACKGROUND_CHECK_STATUS_PENDING, User
from user.tests import create_user

VENDOR = 'vendor'
URL = DJANGO_SETTINGS.get('LAIKA_WEB_REDIRECT')


def get_checkr_data_mock(file_name):
    with open(f'integration/tests/response_mocks/{file_name}') as f:
        return json.load(f)


def create_lo_background_check(
    organization, connection_account_auth, data=None, vendor=None
):
    if data is None:
        data = {'Id': 'e44aa283528e6fde7d542194', 'Status': 'clear'}
    vendor = vendor if vendor else VENDOR
    connection_account = create_connection_account(
        vendor,
        organization=organization,
        authentication=connection_account_auth,
        created_by=create_user(organization, email='heylaika1@heylaika.com'),
    )
    lo_type = resolve_laika_object_type(organization, BACKGROUND_CHECK)
    laika_object = LaikaObject.objects.create(
        object_type=lo_type, data=data, connection_account=connection_account
    )
    return lo_type, laika_object


@pytest.mark.functional
def test_dashboard_redirect(connection_account):
    connection_account.organization.state = ACTIVE
    expected = f'{URL}/integrations/{VENDOR}/{connection_account.control}'
    assert laika_web_redirect(connection_account) == expected


@pytest.mark.functional
def test_onboarding_redirect(connection_account):
    connection_account.organization.state = ONBOARDING
    expected = f'{URL}/integrations/{VENDOR}/{connection_account.control}'
    assert laika_web_redirect(connection_account) == expected


@pytest.fixture()
def connection_account():
    connection_account = create_connection_account(VENDOR)
    return connection_account


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_report_completed_consider(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_report.json')
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'checkr_account_id': checkr_data.get('account_id')},
        vendor='Checkr',
    )

    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    checkr_object = checkr_data.get('data', {}).get('object', {})
    modified_candidate = LaikaObject.objects.get(
        object_type=lo_type, data__Id=checkr_object.get('candidate_id')
    )
    assert request.method == 'POST'
    assert response.status_code == 200
    assert modified_candidate.data.get('Status') == NEEDS_REVIEW_STATUS
    assert (
        modified_candidate.data.get('People Status') == BACKGROUND_CHECK_STATUS_PENDING
    )


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_invitation_completed(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_invitation_completed.json')
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'checkr_account_id': checkr_data.get('account_id')},
        {
            "Id": "60fd47a55f73c5f7e7d59a1e",
            "Email": "leo@heylaika.com",
            "Status": "completed",
            "Package": "driver_pro",
            "Last Name": "Messi",
            "Check Name": "tasker_pro",
            "First Name": "Leo",
            "Source System": "checkr",
            "Connection Name": "Checkr Connection",
        },
        vendor='Checkr',
    )

    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    checkr_object = checkr_data.get('data', {}).get('object', {})
    modified_candidate = LaikaObject.objects.get(
        object_type=lo_type, data__Id=checkr_object.get('candidate_id')
    )
    assert request.method == 'POST'
    assert response.status_code == 200
    assert modified_candidate.data.get('Initiation Date') == checkr_object.get(
        'completed_at'
    )
    assert modified_candidate.data.get('Package') == checkr_object.get('package')
    assert modified_candidate.data.get('First Name') == "Leo"
    assert modified_candidate.data.get('Email') == "leo@heylaika.com"


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_candidate_updated(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_candidate_updated.json')
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'checkr_account_id': checkr_data.get('account_id')},
        {
            "Id": "58f8e550d991bb000db04005",
            "Email": "leo@heylaika.com",
            "Status": "completed",
            "Package": "driver_pro",
            "Last Name": "Messi",
            "Check Name": "tasker_pro",
            "First Name": "Leo",
            "Source System": "checkr",
            "Link to People Table": {},
        },
        vendor='Checkr',
    )

    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    checkr_object = checkr_data.get('data', {}).get('object', {})
    modified_candidate = LaikaObject.objects.get(
        object_type=lo_type, data__Id=checkr_object.get('id')
    ).data
    assert request.method == 'POST'
    assert response.status_code == 200
    assert modified_candidate.get('Link to People Table') == {}
    assert modified_candidate.get('First Name') == checkr_object.get('first_name')
    assert modified_candidate.get('Last Name') == checkr_object.get('last_name')
    assert modified_candidate.get('Email') == checkr_object.get('email')


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_report_created(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_report_created.json')
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'checkr_account_id': checkr_data.get('account_id')},
        {
            "Id": "58f8e550d991bb000db04005",
            "Email": "leo@heylaika.com",
            "Status": "completed",
            "Package": "tasker_pro",
            "Last Name": "Messi",
            "Check Name": "tasker_pro",
            "First Name": "Leo",
            "Estimated Completion Date": "",
        },
        vendor='Checkr',
    )

    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    checkr_object = checkr_data.get('data', {}).get('object', {})
    modified_candidate = LaikaObject.objects.get(
        object_type=lo_type, data__Id=checkr_object.get('id')
    ).data
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS')
    assert Alert.objects.filter(type=alert_type).count() == 0
    assert request.method == 'POST'
    assert response.status_code == 200
    assert modified_candidate.get('Package') == checkr_object.get('package')
    assert modified_candidate.get('Estimated Completion Date') == checkr_object.get(
        'estimated_completion_time'
    )
    assert modified_candidate.get('Email') == "leo@heylaika.com"


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_success_candidate_update_type(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_candidate.json')
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'checkr_account_id': checkr_data.get('account_id')},
        {'Id': '60fd47a55f73c5f7e7d59a1e', 'Email': 'test@heylaika.com'},
        vendor='Checkr',
    )
    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)
    checkr_object = checkr_data.get('data', {}).get('object', {})
    modified_candidate = LaikaObject.objects.get(
        object_type=lo_type, data__Id=checkr_object.get('id')
    )

    assert request.method == 'POST'
    assert response.status_code == 200
    assert modified_candidate.data.get('Email') == checkr_object.get('email')


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_success_candidate_update_type_and_create_alert(
    graphql_organization,
):
    checkr_data = get_checkr_data_mock('checkr_response_invitation_completed.json')
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'checkr_account_id': checkr_data.get('account_id')},
        {'Id': '60fd47a55f73c5f7e7d59a1e', 'Email': 'test@heylaika.com'},
        vendor='Checkr',
    )
    admin_user = create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='john',
    )
    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    checkr_object = checkr_data.get('data', {}).get('object', {})
    modified_candidate = LaikaObject.objects.get(
        object_type=lo_type, data__Id=checkr_object.get('id')
    )
    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_CHANGED_STATUS')
    alert = Alert.objects.filter(type=alert_type)
    assert request.method == 'POST'
    assert response.status_code == 200
    assert modified_candidate.data.get('Package') == checkr_object.get('package')
    assert alert.count() == 1
    assert alert[0].receiver == admin_user
    assert alert[0].sender_name == 'Admin'


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_report_completed_update_user_linked(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_report.json')
    admin_user = create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='john',
    )
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'checkr_account_id': checkr_data.get('account_id')},
        {
            'Id': 'e44aa283528e6fde7d542194',
            'Email': 'test@heylaika.com',
            "Link to People Table": {
                "id": admin_user.id,
                "email": admin_user.email,
                "lastName": admin_user.last_name,
                "username": admin_user.username,
                "firstName": admin_user.first_name,
            },
        },
        vendor='Checkr',
    )

    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    checkr_object = checkr_data.get('data', {}).get('object', {})
    modified_candidate = LaikaObject.objects.get(
        object_type=lo_type, data__Id=checkr_object.get('id')
    )
    user_updated = User.objects.get(id=admin_user.id)
    assert request.method == 'POST'
    assert response.status_code == 200
    assert modified_candidate.data.get('Status') == NEEDS_REVIEW_STATUS
    assert (
        modified_candidate.data.get('People Status') == BACKGROUND_CHECK_STATUS_PENDING
    )
    assert user_updated.background_check_status == BACKGROUND_CHECK_STATUS_PENDING
    assert user_updated.background_check_passed_on is not None


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_unsuccess(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_report.json')

    request = RequestFactory().get(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    assert request.method == 'GET'
    assert response.status_code == 200


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_account_credentialed(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_account.credentialed.json')
    connection_account_id = checkr_data.get('account_id')
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'checkr_account_id': connection_account_id},
        {'Id': '60fd47a55f73c5f7e7d59a1e', 'Email': 'test@heylaika.com'},
        vendor='Checkr',
    )

    admin_user = create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='john',
    )

    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_ACCOUNT_CREDENTIALED')
    alert = Alert.objects.filter(type=alert_type)

    connection_account = ConnectionAccount.objects.get(
        organization=graphql_organization,
        authentication__checkr_account_id=connection_account_id,
    )

    assert request.method == 'POST'
    assert response.status_code == 200
    assert alert.count() == 1
    assert alert[0].receiver == admin_user
    assert alert[0].sender_name == 'Admin'
    assert connection_account.authentication.get('authorized') is True


@pytest.mark.functional(permissions=['objects.change_laikaobject'])
def test_webhook_checkr_token_deauthorized(graphql_organization):
    checkr_data = get_checkr_data_mock('checkr_response_token.deauthorized.json')
    access_token = encrypt_value(
        checkr_data.get('data', {}).get('object', {}).get('access_code')
    )
    lo_type, _ = create_lo_background_check(
        graphql_organization,
        {'access_token': access_token},
        {'Id': '60fd47a55f73c5f7e7d59a1e', 'Email': 'test@heylaika.com'},
        vendor='Checkr',
    )

    admin_user = create_user(
        graphql_organization,
        email='jhon@heylaika.com',
        role=ROLE_ADMIN,
        first_name='john',
    )

    request = RequestFactory().post(
        '/integration/checkr/incoming', checkr_data, content_type=JSON_CONTENT_TYPE
    )
    response = webhook_checkr(request)

    alert_type = ALERT_TYPES.get('LO_BACKGROUND_CHECK_TOKEN_DEAUTHORIZED')
    alert = Alert.objects.filter(type=alert_type)
    connection_account = ConnectionAccount.objects.get(
        organization=graphql_organization, authentication__access_token=access_token
    )

    assert request.method == 'POST'
    assert response.status_code == 200
    assert alert.count() == 1
    assert alert[0].receiver == admin_user
    assert alert[0].sender_name == 'Admin'
    assert connection_account.authentication.get('authorized') is False
