import http
from unittest.mock import patch

import pytest
from httmock import HTTMock, response, urlmatch
from requests import RequestException

from organization.salesforce.salesforce_rest_client import (
    get_access_token,
    get_all_salesforce_organizations,
    get_salesforce_organizations_ready_to_sync,
    get_user_details,
    update_polaris_id_in_synced_orgs,
    update_salesforce_organization,
)
from organization.salesforce.salesforce_types import SalesforceAccountType

INSTANCE_URL = 'https://heylaika--partial.sandbox.my.salesforce.com'
CONTENT_TYPE = 'application/json'
USER_SALESFORCE_URL = '/services/data/v46.0/sobjects/User/0034g033000noryNNN'


def generate_mock_auth():
    access_token = 'my_token'
    auth = {'Authorization': 'Bearer ' + access_token}
    instance_url = INSTANCE_URL
    return dict(auth=auth, instance_url=instance_url)


@pytest.mark.functional
def test_get_sfdc_access_token():
    @urlmatch(netloc=r'test.salesforce.com', path='/services/oauth2/token')
    def get_res_access_token(url, request):
        headers = {'content-type': CONTENT_TYPE}
        content = {
            'access_token': (
                '00D54000000kW6i!AR0AQEaFLIOKiOn9k1NdrBKl2ltSHmgTaVy2Nde7'
                '8MCn4XjNLjSlDwS3esf3mQs7FxOpHKMrB9sAjQb7LoThqTJSkHokQIYP'
            ),
            'instance_url': INSTANCE_URL,
            'id': (
                'https://test.salesforce.com/id/00D54000000kW6iEAE/0054P00000As0JvQAJ'
            ),
            'token_type': 'Bearer',
            'issued_at': '1665610417460',
            'signature': 'Uxef9EHz2+aureuMHnFQe05YcCLXkgWVI7YauQVb5jE=',
        }
        return response(http.HTTPStatus.ACCEPTED, content, headers, None, 5, request)

    with HTTMock(get_res_access_token):
        get_result = get_access_token()

    assert get_result.get('instance_url') == INSTANCE_URL


@pytest.mark.functional
def test_get_sfdc_access_token_with_error():
    @urlmatch(netloc=r'test.salesforce.com', path='/services/oauth2/token')
    def get_res_access_token(url, request):
        headers = {'content-type': CONTENT_TYPE}
        content = {
            "error": "invalid_grant",
            "error_description": "authentication failure",
        }
        return response(http.HTTPStatus.BAD_REQUEST, content, headers, None, 2, request)

    with HTTMock(get_res_access_token):
        get_result = get_access_token()

    assert get_result is None


@pytest.mark.functional
def test_get_request_exception_sfdc_access_token():
    with patch('requests.post') as post_mock:
        post_mock.side_effect = RequestException(
            'Error getting access token from Salesforce'
        )
        get_result = get_access_token()
        assert get_result is None


@pytest.mark.functional
def test_get_exception_sfdc_access_token():
    with patch('requests.post') as post_mock:
        post_mock.side_effect = Exception('Error getting access token from Salesforce')
        get_result = get_access_token()
        assert get_result is None


@pytest.mark.functional
def test_get_user_details():
    @urlmatch(
        netloc=r'heylaika--partial.sandbox.my.salesforce.com',
        path=r'/services/data/v55.0/sobjects/User/0053g000000noryAAA',
    )
    def get_res_user_details(url, request):
        return response(
            status_code=http.HTTPStatus.ACCEPTED,
            content={
                'attributes': {
                    'type': 'User',
                    'url': USER_SALESFORCE_URL,
                },
                'Id': '0053g000000noryAAA',
                'Username': 'laika-test@heylaika.com.partial',
                'LastName': 'Valid',
                'FirstName': 'User',
                'Name': 'Valid User',
                'Email': 'laika-test@heylaika.com',
            },
        )

    with HTTMock(get_res_user_details):
        user_id = '0053g000000noryAAA'
        get_result = get_user_details(user_id, generate_mock_auth())

    assert get_result.get('Email') == 'laika-test@heylaika.com'


@pytest.mark.functional
def test_get_user_details_not_found():
    @urlmatch(
        netloc=r'heylaika--partial.sandbox.my.salesforce.com',
        path=r'/services/data/v55.0/sobjects/User/0053g000000noryAbc',
    )
    def resource_not_found(url, request):
        return response(
            status_code=http.HTTPStatus.NOT_FOUND,
            content={
                "errorCode": "NOT_FOUND",
                "message": (
                    "Provided external ID field does not exist or is not accessible:"
                    " 0053g000000noryAAAv"
                ),
            },
        )

    with HTTMock(resource_not_found):
        get_result = get_user_details('0053g000000noryAbc', generate_mock_auth())

    assert get_result is None


@pytest.mark.functional
def test_get_all_salesforce_organizations():
    @urlmatch(
        scheme='http',
        netloc=r'heylaika--partial.sandbox.my.salesforce.com',
        path='/services/data/v55.0/query/',
        query=(
            'q=SELECT+Account_ID_18_char__c,name,Compliance_Architect__c,'
            'Customer_Success_Manager__c+from+Account+where+'
            'Account_ID_18_char__c!=null'
        ),
        method='GET',
    )
    def get_res_all_orgs(url, request):
        return response(
            status_code=http.HTTPStatus.ACCEPTED,
            content={
                'totalSize': '3',
                'done': 'false',
                'nextRecordsUrl': '/services/data/v55.0/query/01g5400000rvUfAAAU-2000',
                'records': [
                    {
                        'attributes': {
                            'type': 'Account',
                            'url': (
                                '/services/data/v55.0/'
                                'sobjects/Account/0013g00000f1CzSAAU'
                            ),
                        },
                        'Account_ID_18_char__c': '0013g00000f1CzSAAU',
                        'Name': 'MobiLoud',
                        'Compliance_Architect__c': 'null',
                        'Customer_Success_Manager__c': 'null',
                    },
                    {
                        'attributes': {
                            'type': 'Account',
                            'url': (
                                '/services/data/v55.0/'
                                'sobjects/Account/0013g00000f1CzTAAU'
                            ),
                        },
                        'Account_ID_18_char__c': '0013g00000f1CzTAAU',
                        'Name': 'Showit',
                        'Compliance_Architect__c': 'null',
                        'Customer_Success_Manager__c': 'null',
                    },
                ],
            },
            headers={'content-type': CONTENT_TYPE, 'Set-Cookie': 'foo=bar;'},
        )

    with HTTMock(get_res_all_orgs):
        get_result = get_all_salesforce_organizations(generate_mock_auth())

    assert get_result[0].get('errorCode') == 'INVALID_SESSION_ID'


@pytest.mark.functional
def test_get_salesforce_organizations_ready_to_sync():
    @urlmatch(
        netloc=r'heylaika--partial.sandbox.my.salesforce.com',
        path=r'/services/apexrest/accounts/polaris',
    )
    def sync_salesforce_data(url, request):
        return response(
            status_code=http.HTTPStatus.ACCEPTED,
            content=[
                {
                    "attributes": {
                        "type": "Account",
                        "url": (
                            "/services/data/v56.0/sobjects/Account/0013g00000hg1DOAAY"
                        ),
                    },
                    "Account_ID_18_char__c": "abcdefgh123",
                    "Name": "Company 1",
                    "Compliance_Architect__c": "00sdfsdfsdfdsf",
                    "Customer_Success_Manager__c": "0055sdfdsfdfAAB",
                    "Account_Status__c": "Active Trial",
                    "LastModifiedById": "005dsfsdfdfv1qpAAB",
                    "Id": "0fsdsdfsdf00hg1DOAAY",
                    "Compliance_Architect__r": {
                        "attributes": {
                            "type": "User",
                            "url": (USER_SALESFORCE_URL),
                        },
                        "Id": "0dsfdf000Dv1qpAAB",
                        "Email": "user.valid@heylaika.com",
                    },
                    "Customer_Success_Manager__r": {
                        "attributes": {
                            "type": "User",
                            "url": (USER_SALESFORCE_URL),
                        },
                        "Id": "0055400000Dv1qpAAB",
                        "Email": "user.valid@heylaika.com",
                    },
                    "LastModifiedBy": {
                        "attributes": {
                            "type": "User",
                            "url": (USER_SALESFORCE_URL),
                        },
                        "Id": "00554ssdfrdpAAB",
                        "Name": "Laika User",
                    },
                },
                {
                    "attributes": {
                        "type": "Account",
                        "url": (
                            "/services/data/v56.0/sobjects/Account/0013g00000hiS2bAAE"
                        ),
                    },
                    "Account_ID_18_char__c": "zxcvefgh123",
                    "Name": "Company 2",
                    "Website": "website-company2.com",
                    "Compliance_Architect__c": "005sdffsdDv1qpAAB",
                    "Customer_Success_Manager__c": "00554sdfsdv1qpAAB",
                    "Current_Contract_Start_Date_Auto__c": "2022-08-19",
                    "Account_Status__c": "Customer",
                    "LastModifiedById": "005sdffDv1qpAAB",
                    "Id": "0013sdfffS2bAAE",
                    "Compliance_Architect__r": {
                        "attributes": {
                            "type": "User",
                            "url": USER_SALESFORCE_URL,
                        },
                        "Id": "0055sdfsfv1qpAAB",
                        "Email": "user.laika@heylaika.com",
                    },
                    "Customer_Success_Manager__r": {
                        "attributes": {
                            "type": "User",
                            "url": (USER_SALESFORCE_URL),
                        },
                        "Id": "0055sdfs1qpAAB",
                        "Email": "user.laika@heylaika.com",
                    },
                    "LastModifiedBy": {
                        "attributes": {
                            "type": "User",
                            "url": USER_SALESFORCE_URL,
                        },
                        "Id": "005sfdf00Dv1qpAAB",
                        "Name": "User Laika",
                    },
                },
            ],
        )

    with HTTMock(sync_salesforce_data):
        my_orgs_list = ['abcdefgh123', 'zxcvefgh123']
        get_result = get_salesforce_organizations_ready_to_sync(
            generate_mock_auth(), my_orgs_list
        )

    assert get_result[0].get('Account_ID_18_char__c') == 'abcdefgh123'
    assert get_result[1].get('Account_ID_18_char__c') == 'zxcvefgh123'


@pytest.mark.functional
def test_update_salesforce_organization():
    @urlmatch(
        netloc=r'heylaika--partial.sandbox.my.salesforce.com',
        path=r'/services/apexrest/accounts/polaris',
    )
    def put_org_to_sf(url, request):
        return response(
            status_code=http.HTTPStatus.ACCEPTED,
            content={
                "attributes": {
                    "type": "Account",
                    "url": "/services/data/v56.0/sobjects/Account/abcdefgh123",
                },
                "Id": "abcdefgh123",
                "Name": "Company Test Updated",
                "Website": "https://website.com",
            },
        )

    with HTTMock(put_org_to_sf):
        sfdc_id = 'abcdefgh123'
        payload = SalesforceAccountType(
            name='Company Test Updated',
            csm='user.valid@test.com',
            ca='user.valid@test.com',
            website='https://website.com',
        )
        get_result = update_salesforce_organization(
            generate_mock_auth(), sfdc_id, payload
        )

    assert get_result.get('Id') == 'abcdefgh123'
    assert get_result.get('Name') == 'Company Test Updated'


@pytest.mark.functional
def test_update_polaris_id_in_synced_orgs():
    @urlmatch(
        netloc=r'heylaika--partial.sandbox.my.salesforce.com',
        path=r'/services/apexrest/accounts/polaris',
    )
    def put_polaris_id_to_sf(url, request):
        return response(status_code=http.HTTPStatus.ACCEPTED)

    with HTTMock(put_polaris_id_to_sf):
        payload = [{"polarisID": "testID", "salesforceID": "testID”"}]
        get_result = update_polaris_id_in_synced_orgs(generate_mock_auth(), payload)

    assert get_result == http.HTTPStatus.ACCEPTED
