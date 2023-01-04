import datetime
from unittest.mock import patch

import pytest

from feature.constants import onboarding_v2_flag
from organization.constants import COMPLETED_STATE
from organization.models import ACTIVE, ONBOARDING, TRIAL, Onboarding, Organization
from organization.salesforce.constants import ACTIVE_TRIAL, CUSTOMER, STATES
from organization.salesforce.implementation import (
    map_org_status,
    update_or_create_organization,
)
from organization.tests import create_organization
from user.tests import create_user

users_mock = {
    'compliance_architect': 'ca-test@heylaika.com',
    'customer_success_manager': 'csm-test@heylaika.com',
}


def string_date_to_datetime(date: str):
    return datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')


EXPECTED_START_DATE_STRING = string_date_to_datetime('2020-10-10 12:00:00')
ORG_NAME = 'Company'
ORG_WEBSITE = 'https://companyheylaika.com/'
VALID_STATUS = 'Customer'
INVALID_STATUS = 'Open'


def create_mock_response(users: dict, state: str) -> dict:
    return dict(
        Account_ID_18_char__c='123',
        Name='Company',
        Website=ORG_WEBSITE,
        Compliance_Architect__r=users.get('compliance_architect'),
        Customer_Success_Manager__r=users.get('customer_success_manager'),
        Current_Contract_Start_Date_Auto__c='2020-10-10 12:00:00',
        Account_Status__c=state,
        LastModifiedById='User',
    )


def create_org_with_ca_and_csm(csm_user, ca_user, sfdc_id) -> Organization:
    return create_organization(
        name='Company',
        website=ORG_WEBSITE,
        customer_success_manager_user=csm_user,
        compliance_architect_user=ca_user,
        sfdc_id=sfdc_id,
    )


@pytest.fixture
def users(graphql_organization):
    user_1 = create_user(graphql_organization, [], 'ca-test@heylaika.com')
    user_2 = create_user(graphql_organization, [], 'csm-test@heylaika.com')
    return user_1, user_2


@pytest.mark.functional
@patch('organization.salesforce.implementation.post_info_message')
@patch('organization.tasks.create_super_admin_users')
def test_create_organization_with_ca_and_csm(
    create_super_admin_users_mock,
    post_info_message_mock,
    users,
    graphql_organization,
):
    user_1, user_2 = users
    res = create_mock_response(users_mock, VALID_STATUS)

    org_test, _ = update_or_create_organization(res)
    assert org_test.sfdc_id == '123'
    assert org_test.name == ORG_NAME
    assert org_test.website == ORG_WEBSITE
    assert org_test.compliance_architect_user_id == user_1.id
    assert org_test.customer_success_manager_user_id == user_2.id
    assert org_test.contract_sign_date == EXPECTED_START_DATE_STRING
    assert org_test.state == STATES[VALID_STATUS]
    post_info_message_mock.assert_called_once()

    create_super_admin_users_mock.assert_called_once()


@pytest.mark.functional
def test_create_organization_without_ca_and_csm(graphql_organization):
    res = create_mock_response(
        dict(compliance_architect=None, customer_success_manager=None), VALID_STATUS
    )

    org_test, _ = update_or_create_organization(res)
    assert org_test is None


@pytest.mark.functional
@patch('organization.mutations.update_ca_user')
@patch('organization.mutations.update_csm_user')
def test_update_organization_with_ca_and_csm(
    update_ca_user_mock, update_csm_user_mock, users
):
    new_csm, new_ca = users
    res = create_mock_response(users_mock, VALID_STATUS)

    org_to_test = create_org_with_ca_and_csm(
        csm_user=new_csm, ca_user=new_ca, sfdc_id='123'
    )

    org_to_test.state = ACTIVE
    org_to_test.save()

    org_test, _ = update_or_create_organization(res)

    assert update_ca_user_mock.called
    assert update_csm_user_mock.called

    assert org_test.sfdc_id == '123'
    assert org_test.name == ORG_NAME
    assert org_test.website == ORG_WEBSITE
    assert org_test.customer_success_manager_user_id == new_csm.id
    assert org_test.compliance_architect_user_id == new_ca.id
    assert org_test.contract_sign_date == EXPECTED_START_DATE_STRING
    assert org_test.state == ACTIVE


@pytest.mark.functional
def test_update_organization_keep_state(graphql_organization):
    sfdc = '123'
    graphql_organization.state = ONBOARDING
    graphql_organization.sfdc_id = sfdc
    graphql_organization.save()

    res = dict(
        Account_ID_18_char__c=sfdc,
        Account_Status__c='Customer',
        LastModifiedById='User',
    )

    org_test, _ = update_or_create_organization(res)

    assert org_test.sfdc_id == sfdc
    assert org_test.state == ONBOARDING


@pytest.mark.functional
def test_update_organization_without_ca_and_csm(users, graphql_organization):
    user_1, user_2 = users

    res = create_mock_response(
        dict(
            compliance_architect='ca-test-invalid@heylaika.com',
            customer_success_manager='csm-test-invalid@heylaika.com',
        ),
        VALID_STATUS,
    )

    create_org_with_ca_and_csm(user_1, user_2, '123')

    org_test, _ = update_or_create_organization(res)
    assert org_test.customer_success_manager_user_id == user_1.id
    assert org_test.compliance_architect_user_id == user_2.id


@pytest.mark.functional
def test_create_org_with_invalid_state(users, graphql_organization):
    res = create_mock_response(users_mock, INVALID_STATUS)

    org_test, _ = update_or_create_organization(res)
    assert org_test is None


@pytest.mark.functional
def test_create_org_with_duplicate_website(users, graphql_organization):
    user_1, user_2 = users
    res = create_mock_response(users_mock, VALID_STATUS)
    create_org_with_ca_and_csm(user_1, user_2, '345')
    org_test, _ = update_or_create_organization(res)

    assert org_test is None


@pytest.mark.functional
def test_map_org_status_active_or_onboarding(graphql_organization):
    assert not map_org_status(graphql_organization, '')

    graphql_organization.state = 'ACTIVE'
    graphql_organization.save()
    assert not map_org_status(graphql_organization, '')


@pytest.mark.functional
def test_map_org_status_trial_to_onboarding(graphql_organization):
    graphql_organization.state = TRIAL
    graphql_organization.save()
    assert map_org_status(graphql_organization, CUSTOMER) == ONBOARDING


@pytest.mark.functional
def test_map_org_status_trial_to_active(graphql_organization):
    graphql_organization.state = TRIAL
    graphql_organization.save()
    onboarding = Onboarding.objects.filter(
        organization_id=graphql_organization.id
    ).first()

    assert onboarding

    if graphql_organization.is_flag_active(onboarding_v2_flag):
        onboarding.state_v2 = COMPLETED_STATE
    else:
        onboarding.state = COMPLETED_STATE
    onboarding.save()

    assert map_org_status(graphql_organization, CUSTOMER) == ACTIVE


@pytest.mark.functional
def test_map_org_status_trial_to_trial(graphql_organization):
    graphql_organization.state = TRIAL
    graphql_organization.save()

    assert not map_org_status(graphql_organization, ACTIVE_TRIAL)


@pytest.mark.functional
def test_map_org_status_invalid(graphql_organization):
    graphql_organization.state = TRIAL
    graphql_organization.save()

    assert not map_org_status(graphql_organization, '')
