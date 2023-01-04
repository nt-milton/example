import json
import logging
from datetime import date, datetime, timedelta
from typing import Tuple
from unittest.mock import patch

import django.utils.timezone as timezone
import pytest
from django.contrib.admin import AdminSite
from django.contrib.auth.hashers import identify_hasher, make_password
from django.contrib.auth.models import Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import models
from django.test import Client, RequestFactory

from action_item.models import ActionItem, ActionItemStatus
from feature.constants import okta_feature_flag
from laika.settings import LOGIN_API_KEY
from organization.models import Organization
from organization.tests import create_organization
from user.admin import ConciergeAdmin
from user.constants import ALL_HEADERS, ROLE_ADMIN
from user.helpers import (
    assign_user_to_organization_vendor_stakeholders,
    calculate_user_status,
    manage_cognito_user,
    manage_okta_user,
)
from user.models import Concierge, User
from user.mutations_schema.bulk_invite_users import calc_successful_rows
from user.tests import create_user
from user.utils.email import format_super_admin_email, get_delegation_path
from user.views import (
    clean_users_to_export,
    convert_user_date_fields_to_str,
    get_policies_evidence,
    map_user_row,
)
from vendor.models import OrganizationVendor, OrganizationVendorStakeholder

logger = logging.getLogger(__name__)


@pytest.fixture
def organization_with_okta_flag_on() -> Organization:
    return create_organization(flags=[okta_feature_flag], name='Test Org')


@pytest.fixture
def okta_user(organization_with_okta_flag_on) -> User:
    return create_user(organization_with_okta_flag_on)


@pytest.fixture
def organization_with_out_okta_flag_on():
    return create_organization(flags=[], name='Test Org')


@pytest.fixture
def cognito_user(organization_with_out_okta_flag_on):
    return create_user(organization_with_out_okta_flag_on)


@pytest.fixture
def organization_vendor_stakeholder(graphql_organization, graphql_user, vendor):
    organization_vendor = OrganizationVendor.objects.create(
        organization=graphql_organization, vendor=vendor
    )
    organization_vendor_stakeholder = OrganizationVendorStakeholder.objects.create(
        sort_index=1,
        organization_vendor=organization_vendor,
        stakeholder=graphql_user,
    )
    return organization_vendor, organization_vendor_stakeholder


def test_calc_successful_rows():
    mock_sheet_max_row = 16
    mock_ignored_rows = [1, 2, 3]
    mock_failed_rows = [4, 5, 6]

    actual = calc_successful_rows(
        mock_sheet_max_row, mock_ignored_rows, mock_failed_rows
    )

    expected = 8

    assert actual == expected


@pytest.mark.functional()
def test_set_empty_role_for_partial_users(graphql_user):
    graphql_user.is_active = False
    graphql_user.save()

    result = clean_users_to_export([graphql_user])

    assert '' == result[0].role


@pytest.mark.functional()
def test_get_policies_evidence(graphql_organization, graphql_user):
    user1 = create_user(
        graphql_organization,
        email='john1@superadmin.com',
    )
    user2 = create_user(
        graphql_organization,
        email='john2@superadmin.com',
    )
    name1, name2 = 'Policy1', 'Policy2'
    action_item1 = ActionItem.objects.create(
        due_date=date.today(),
        status=ActionItemStatus.PENDING,
        name=name1,
        metadata={
            "seen": False,
            "type": "policy",
        },
    )
    action_item1.assignees.add(user1)
    today = date.today()
    action_item2 = ActionItem.objects.create(
        due_date=today,
        completion_date=today,
        status=ActionItemStatus.COMPLETED,
        name=name2,
        metadata={
            "seen": False,
            "type": "policy",
        },
    )
    action_item2.assignees.add(user2)

    result = get_policies_evidence([user1, user2])

    assert name1 in result[user1.id][1][0]  # Unacknowledged Policies
    assert (
        f'{name2}({today.isoformat()})' in result[user2.id][0][0]
    )  # Acknowledgement Policies


@pytest.mark.functional()
def test_map_user_row_manager(graphql_user):
    graphql_user.manager = graphql_user
    graphql_user.save()
    result = map_user_row(ALL_HEADERS, graphql_user)

    assert graphql_user.email == result['manager_email']


@pytest.mark.functional()
@pytest.mark.parametrize(
    'field_key, expected, received',
    [
        ('role', 'Admin', 'OrganizationAdmin'),
        ('employment_type', 'Employee', 'employee'),
        ('employment_subtype', 'Full-time', 'full_time'),
        ('background_check_status', 'N/A', 'na'),
        ('employment_status', 'Potential Hire', 'potential_hire'),
    ],
)
def test_map_user_row_choices(field_key, expected, received, graphql_user):
    graphql_user.manager = graphql_user
    setattr(graphql_user, field_key, received)
    result = map_user_row(ALL_HEADERS, graphql_user)

    assert expected == result.get(field_key)


@pytest.mark.functional()
@patch('laika.aws.cognito.get_user', return_value={'username': 'new_username'})
@patch('laika.okta.api.OktaApi.get_user_by_email', return_value=None)
def test_api_key_decorator(get_user_mock, get_user_by_email_mock):
    response = Client(
        HTTP_ORIGIN='http://localhost:3000', HTTP_AUTHORIZATION=LOGIN_API_KEY
    ).get('/user/user_idp?username=fake@email.com')
    assert response
    assert response.status_code == 200
    get_user_by_email_mock.assert_called_once()
    get_user_mock.assert_called_once()
    assert (
        str(response.content.decode('UTF-8')) == '{"idp": "COGNITO", "expired": false}'
    )


@pytest.mark.functional()
def test_convert_user_date_fields_to_str(graphql_user):
    '''
    If this test fail, make sure you update the list of fields in the
    'clean_user_date_fields' function.
    We need this because export People would fail if we pass a Datetime
    type instead of a string
    '''
    fields = User._meta.get_fields()
    cleaned_user = convert_user_date_fields_to_str(graphql_user)

    for field in fields:
        if models.DateTimeField != type(field):
            continue
        try:
            value_type = type(getattr(cleaned_user, field.name))
        except AttributeError:
            pass
        assert str == value_type


@pytest.mark.functional
@patch('laika.aws.cognito.get_user', return_value=None)
@patch(
    'user.admin.create_cognito_concierge_user',
    return_value={'username': 'new_username', 'temporary_password': 'pwd'},
)
@patch('user.admin.send_concierge_user_email_invitation')
def test_save_concierge_model(
    send_concierge_user_email_invitation_mock,
    create_cognito_concierge_user_mock,
    get_user_mock,
):
    assert_get_cognito_user(get_user_mock, execute_test())
    assert_create_and_send(
        create_cognito_concierge_user_mock, send_concierge_user_email_invitation_mock
    )


@pytest.mark.functional
@patch('user.admin.cognito.get_user', return_value=True)
@patch('user.admin.delete_cognito_users')
@patch(
    'user.admin.create_cognito_concierge_user',
    return_value={'username': 'new_username', 'temporary_password': 'pwd'},
)
@patch('user.admin.send_concierge_user_email_invitation')
def test_save_concierge_model_delete_cognito_user(
    send_concierge_user_email_invitation_mock,
    create_cognito_concierge_user_mock,
    delete_cognito_users_mock,
    get_user_mock,
):
    obj = execute_test()
    assert_get_cognito_user(get_user_mock, obj)

    delete_cognito_users_mock.assert_called_once()
    assert ([obj.user.email],) == delete_cognito_users_mock.call_args.args

    assert_create_and_send(
        create_cognito_concierge_user_mock, send_concierge_user_email_invitation_mock
    )


def test_hashed_pass_is_not_overwritten():
    raw_password = '123'
    hashed_password = make_password(raw_password)
    user = User()
    user.password = hashed_password
    with patch('django.contrib.auth.models.AbstractUser.save'):
        user.save()
    hasher = identify_hasher(hashed_password)
    assert hasher.verify(raw_password, hashed_password)


@pytest.mark.django_db
def test_calculate_user_status_active(graphql_organization):
    user = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=timezone.now(),
    )
    user.last_login = datetime.now()
    user.save()

    status = calculate_user_status(user)
    assert status == 'ACTIVE'


@pytest.mark.django_db
def test_calculate_user_status_invitation_expired(graphql_organization):
    THIRTY_FIVE_DAYS = 35
    user = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=timezone.now() - timedelta(THIRTY_FIVE_DAYS),
    )

    status = calculate_user_status(user)
    assert status == 'INVITATION_EXPIRED'


@pytest.mark.django_db
def test_calculate_user_status_password_expired(graphql_organization):
    user = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=None,
        password_expired=True,
    )

    status = calculate_user_status(user)
    assert status == 'PASSWORD_EXPIRED'


@pytest.mark.django_db
def test_calculate_user_status_pending(graphql_organization):
    user = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=timezone.now(),
    )

    status = calculate_user_status(user)
    assert status == 'PENDING_INVITATION'


@pytest.mark.django_db
@patch('laika.okta.api.OktaApi.get_user_by_email')
@patch('laika.okta.api.OktaApi.delete_user')
@patch('laika.okta.api.OktaApi.create_user')
@patch('user.helpers.add_user_to_group')
@patch('user.helpers.send_email_invite')
def test_manage_okta_user(
    send_email_invite_mock,
    add_user_to_group_mock,
    create_user_mock,
    delete_user_mock,
    get_user_by_email_mock,
    organization_with_okta_flag_on,
):
    user = create_user(
        organization_with_okta_flag_on,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=timezone.now(),
    )

    get_user_by_email_mock.return_value = user
    create_user_mock.return_value = (user, 'temp_password')

    user, _ = manage_okta_user(user)

    get_user_by_email_mock.assert_called_once()
    delete_user_mock.assert_called_once()
    create_user_mock.assert_called_once()
    add_user_to_group_mock.assert_called_once()
    send_email_invite_mock.assert_called_once()

    assert user.is_active is True
    assert user.invitation_sent is not None


@pytest.mark.django_db
@patch('laika.aws.cognito.get_user')
@patch('user.helpers.delete_cognito_users')
@patch('user.helpers.create_cognito_user')
@patch('user.helpers.add_user_to_group')
@patch('user.helpers.send_email_invite')
def test_manage_cognito_user(
    send_email_invite_mock,
    add_user_to_group_mock,
    create_cognito_user_mock,
    delete_cognito_users_mock,
    get_user_mock,
    organization_with_okta_flag_on,
):
    user = create_user(
        organization_with_okta_flag_on,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='johnC',
        last_name='doeC',
        invitation_sent=timezone.now(),
    )

    get_user_mock.return_value = user
    create_cognito_user_mock.return_value = dict(
        username='Someusername', temporaryPassword='temp_password'
    )

    user, _ = manage_cognito_user(user)

    get_user_mock.assert_called_once()
    delete_cognito_users_mock.assert_called_once()
    create_cognito_user_mock.assert_called_once()
    add_user_to_group_mock.assert_called_once()
    send_email_invite_mock.assert_called_once()

    assert user.is_active is True
    assert user.invitation_sent is not None


@pytest.mark.functional()
def test_get_user_status(graphql_user):
    response = Client(
        HTTP_ORIGIN='http://localhost:3000', HTTP_AUTHORIZATION=LOGIN_API_KEY
    ).get(f'/user/get_user_status?username={graphql_user.email}')

    content = json.loads(response.content)

    assert content['status'] == 'PENDING_INVITATION'


def get_concierge_admin() -> Tuple[ConciergeAdmin, RequestFactory, Concierge]:
    request_factory = RequestFactory()
    request = request_factory.get('/admin')

    # If you need to test something using messages
    setattr(request, 'session', 'session')
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    concierge_email = 'test@heylaika.com'
    user = User.objects.create(
        email=concierge_email,
        first_name='Test',
        last_name='Laika',
        role='Concierge',
        username=concierge_email,
    )

    user.groups.add(Group.objects.create(name='concierge'))
    obj = Concierge.objects.create(user=user)

    return ConciergeAdmin(Concierge, AdminSite()), request, obj


def execute_test() -> Concierge:
    admin, request, obj = get_concierge_admin()
    admin.save_model(request, obj, None, False)
    return obj


def assert_get_cognito_user(get_user_mock, obj):
    get_user_mock.assert_called_once()
    assert (obj.user.email,) == get_user_mock.call_args.args


def assert_create_and_send(create_user_mock, send_email_mock):
    create_user_mock.assert_called_once()
    send_email_mock.assert_called_once()


def test_format_super_admin_email():
    new_email = format_super_admin_email(
        'admin+laikaapp@heylaika.com', 'https://www.test.com'
    )
    expect_email = 'admin+laikaapp+test@heylaika.com'
    assert expect_email == new_email


def test_get_delegation_path_onbarding_state():
    path = get_delegation_path('ONBOARDING')
    assert path == '/onboarding/automate-compliance'


def test_get_delegation_path_active_state():
    path = get_delegation_path('ACTIVE')
    assert path == '/integrations'


def test_get_delegation_path_active_empty():
    path = get_delegation_path(None)
    assert path == '/integrations'


@pytest.mark.django_db
def test_assign_user_to_organization_vendor_stakeholders(
    organization_vendor_stakeholder, vendor, graphql_organization, graphql_user
):
    organization_vendor = organization_vendor_stakeholder[0]
    organization_vendor_stakeholder = assign_user_to_organization_vendor_stakeholders(
        organization_vendor, graphql_user
    )
    assert organization_vendor.internal_stakeholders.count() == 2
    assert organization_vendor_stakeholder.stakeholder == graphql_user
    assert organization_vendor_stakeholder.organization_vendor == organization_vendor
