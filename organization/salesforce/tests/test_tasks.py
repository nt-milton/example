import http
from unittest.mock import patch

import pytest

from organization.models import Organization
from organization.salesforce.tasks import (
    sync_salesforce_organizations_with_polaris,
    update_polaris_id_to_new_synced_orgs,
)
from organization.tests import create_organization
from user.tests import create_user

test_user_url = '/services/data/v56.0/sobjects/User/testUserId'

SF_ORGS_MOCK = [
    {
        "attributes": {
            "type": "Account",
            "url": "/services/data/v56.0/sobjects/Account/testID",
        },
        "Account_ID_18_char__c": "testID2",
        "Name": "Test Company 2",
        "Website": "https://test-company.com",
        "Compliance_Architect__c": "1234",
        "Customer_Success_Manager__c": "1234",
        "Current_Contract_Start_Date_Auto__c": "2022-09-09",
        "Account_Status__c": "Customer",
        "LastModifiedById": "1234",
        "Id": "testID2",
        "Compliance_Architect__r": {
            "attributes": {
                "type": "User",
                "url": test_user_url,
            },
            "Id": "0054P00000AL9NuQAL",
            "Email": "ca-test@heylaika.com",
        },
        "Customer_Success_Manager__r": {
            "attributes": {
                "type": "User",
                "url": test_user_url,
            },
            "Id": "1234",
            "Email": "csm-test@heylaika.com",
        },
        "LastModifiedBy": {
            "attributes": {
                "type": "User",
                "url": test_user_url,
            },
            "Id": "1234",
            "Name": "UserTest2",
        },
    },
]


@pytest.fixture
def users(graphql_organization):
    user_1 = create_user(graphql_organization, [], 'ca-test@heylaika.com')
    user_2 = create_user(graphql_organization, [], 'csm-test@heylaika.com')
    return user_1, user_2


def create_org(new_csm, new_ca, sfdc_id) -> Organization:
    return create_organization(
        name='Company',
        website='www.valid-website.com',
        customer_success_manager_user=new_csm,
        compliance_architect_user=new_ca,
        sfdc_id=sfdc_id,
    )


@pytest.mark.functional
@patch('organization.salesforce.tasks.update_polaris_id_to_new_synced_orgs')
@patch('organization.salesforce.implementation.post_info_message')
@patch('organization.mutations.update_ca_user')
@patch('organization.mutations.update_csm_user')
@patch(
    'organization.salesforce.tasks.get_organizations_to_sync_from_salesforce',
    return_value=SF_ORGS_MOCK,
)
def test_sync_salesforce_organizations_with_polaris(
    get_organizations_to_sync_from_salesforce_mock,
    update_csm_user_mock,
    update_ca_user_mock,
    post_info_message_mock,
    update_polaris_id_in_synced_orgs_mock,
    users,
):
    new_csm, new_ca = users
    sfdc_id = 'testID2'
    create_org(new_csm, new_ca, sfdc_id)
    expected_success_result = {'success': True}
    sync_result = sync_salesforce_organizations_with_polaris()

    assert sync_result == expected_success_result

    get_organizations_to_sync_from_salesforce_mock.assert_called_once()
    update_csm_user_mock.assert_called_once()
    update_ca_user_mock.assert_called_once()
    update_polaris_id_in_synced_orgs_mock.assert_called_once()


@pytest.mark.functional
@patch(
    'organization.salesforce.tasks.update_polaris_id_in_synced_orgs',
    return_value=http.HTTPStatus.ACCEPTED,
)
@patch('organization.salesforce.tasks.get_access_token', return_value=True)
def test_update_polaris_id_to_new_synced_orgs(
    get_access_token_mock,
    update_polaris_id_in_synced_orgs_mock,
    users,
    graphql_organization,
):
    new_csm, new_ca = users
    sfdc_id = '123'
    orgs_to_update_mock = [sfdc_id]
    create_org(new_csm, new_ca, sfdc_id)
    update_polaris_id_to_new_synced_orgs(orgs_to_update_mock)

    get_access_token_mock.assert_called_once()
    update_polaris_id_in_synced_orgs_mock.assert_called_once()
