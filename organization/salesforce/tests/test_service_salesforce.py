import http
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.test import Client

from conftest import JSON_CONTENT_TYPE
from organization.models import Organization
from organization.salesforce.constants import SALESFORCE_API_KEY
from user.constants import ROLE_SUPER_ADMIN
from user.tests import create_user

MOCK_VALID_USER = 'valid.user@heylaika.com'
MOCK_INVALID_USER = 'invalid.user@heylaika.com'
SALESFORCE_API_KEY_INVALID = 'salesforce-api-key-invalid'

MOCK_JSON_BODY = {
    'Account_ID_18_char__c': '123',
    'Name': 'Company',
    'Website': 'www.company.com',
    'Compliance_Architect__r': MOCK_VALID_USER,
    'Customer_Success_Manager__r': MOCK_VALID_USER,
    'Current_Contract_Start_Date_Auto__c': '2020-10-10 12:00:00',
    'Account_Status__c': 'Customer',
    'LastModifiedById': 'user@heylaika.com',
}

MOCK_INVALID_JSON_BODY = {
    'ID': '123',
    'CompanyName': 'Company',
    'CompanyWebsite': 'www.company.com',
}


WEBHOOK_PATH = '/organization/salesforce'


@pytest.mark.django_db
@patch('organization.salesforce.implementation.post_info_message')
@patch('organization.tasks.create_super_admin_users')
def test_create_salesforce_organization(
    create_super_admin_users_mock, post_info_message_mock, graphql_organization
):
    create_user(
        graphql_organization,
        email=MOCK_VALID_USER,
        role=ROLE_SUPER_ADMIN,
        first_name='Valid',
    )
    response: HttpResponse = Client(HTTP_AUTHORIZATION=SALESFORCE_API_KEY).post(
        path=WEBHOOK_PATH,
        data=MOCK_JSON_BODY,
        content_type=JSON_CONTENT_TYPE,
    )
    organization_created = Organization.objects.get(name='Company', sfdc_id='123')
    assert response.content.decode('utf-8') == str(organization_created.id)
    assert response.status_code == http.HTTPStatus.OK

    create_super_admin_users_mock.assert_called_once()
    post_info_message_mock.assert_called_once()


@pytest.mark.django_db
@patch('organization.views.post_error_message')
def test_error_creating_salesforce_organization(
    post_error_message_mock, graphql_organization
):
    response: HttpResponse = Client(HTTP_AUTHORIZATION=SALESFORCE_API_KEY).post(
        path=WEBHOOK_PATH,
        data=MOCK_JSON_BODY,
        content_type=JSON_CONTENT_TYPE,
    )

    print('ERROR:', response.content.decode('utf-8'))
    assert response.content.decode('utf-8') == 'Failed to sync the organization.'
    assert response.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR

    post_error_message_mock.assert_called_once()


@pytest.mark.django_db
def test_with_invalid_request_method(graphql_organization):
    response: HttpResponse = Client(HTTP_AUTHORIZATION=SALESFORCE_API_KEY).put(
        path=WEBHOOK_PATH,
        data=MOCK_JSON_BODY,
        content_type=JSON_CONTENT_TYPE,
    )
    assert response.status_code == http.HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_with_invalid_fields_in_data_body(graphql_organization):
    response: HttpResponse = Client(HTTP_AUTHORIZATION=SALESFORCE_API_KEY).post(
        path=WEBHOOK_PATH,
        data=MOCK_INVALID_JSON_BODY,
        content_type=JSON_CONTENT_TYPE,
    )
    assert response.status_code == http.HTTPStatus.BAD_REQUEST
