import json

from integration.azure.implementation import (
    AZURE_SYSTEM,
    MicrosoftRequest,
    ServicePrincipal,
    _map_service_account_response_to_laika_object,
    _map_user_response_to_laika_object,
)
from integration.azure.tests.fake_api import (
    organization_response,
    service_principal_response,
    users_response,
)

alias = 'azure test'

CONNECTION_NAME = 'Connection Name'
SOURCE_SYSTEM = 'Source System'
expected = {SOURCE_SYSTEM: AZURE_SYSTEM, CONNECTION_NAME: alias}

user_data = json.loads(users_response())['value'][0]
organization_data = json.loads(organization_response())['value']

admin_roles = {
    'roles': [
        {
            'id': 'dc1aaaa5-ce4a-45e7-9812-42c83a266da4',
            'roleName': 'CustomAdminRole',
            'permissions': ['Microsoft.Compute/cloudServices/write'],
            'roleType': 'CustomRole',
        },
        {
            'id': 'dc1aaaa5-ce4a-45e7-9812-42c83a266da4',
            'roleName': 'Owner',
            'permissions': ['*'],
            'roleType': 'BuiltInRole',
        },
        {
            'id': 'dc1aaaa5-ce4a-45e7-9812-42c83a266da4',
            'roleName': 'User Access Administrator',
            'permissions': [
                '*/read',
                'Microsoft.Authorization/*',
                'Microsoft.Support/*',
            ],
            'roleType': 'BuiltInRole',
        },
    ]
}

reader_roles = {
    'roles': [
        {
            'id': 'dc1aaaa5-ce4a-45e7-9812-42c83a266da4',
            'roleName': 'CustomReaderRole',
            'permissions': [
                'Microsoft.ContainerRegistry/locations/operationResults/read',
                'Microsoft.ContainerRegistry/checkNameAvailability/read',
                'Microsoft.ContainerRegistry/operations/read',
            ],
            'roleType': 'CustomRole',
        }
    ]
}


def test_user_mapping():
    user = user_from_tuple(None, organization_data, reader_roles, user_data)
    expected_response = _user_expected_response()
    lo = _map_user_response_to_laika_object(user, alias)

    assert expected.items() < lo.items()
    assert expected_response == lo


def test_user_mapping_with_admin_roles():
    user = user_from_tuple(None, organization_data, admin_roles, user_data)
    expected_response = _user_with_admin_role_expected_response()
    lo = _map_user_response_to_laika_object(user, alias)

    assert expected.items() < lo.items()
    assert expected_response == lo


def user_from_tuple(groups, organization, roles, user):
    user = MicrosoftRequest(groups, user, organization, roles)
    return user


def _user_expected_response():
    return {
        'Id': 'AZURE-a9343da3-9930-415e-b6e0-ee477bfffefe',
        'First Name': 'Laika',
        'Last Name': 'dev-user',
        'Title': 'Software Engineer',
        'Email': 'laika-dev@onmicrosoft.com',
        'Organization Name': 'azure-organization',
        'Is Admin': False,
        'Roles': 'CustomReaderRole',
        'Mfa Enabled': '',
        'Mfa Enforced': '',
        SOURCE_SYSTEM: AZURE_SYSTEM,
        CONNECTION_NAME: alias,
        'Groups': '',
    }


def _user_with_admin_role_expected_response():
    return {
        'Id': 'AZURE-a9343da3-9930-415e-b6e0-ee477bfffefe',
        'First Name': 'Laika',
        'Last Name': 'dev-user',
        'Title': 'Software Engineer',
        'Email': 'laika-dev@onmicrosoft.com',
        'Organization Name': 'azure-organization',
        'Is Admin': True,
        'Roles': 'CustomAdminRole, Owner, User Access Administrator',
        'Mfa Enabled': '',
        'Mfa Enforced': '',
        SOURCE_SYSTEM: AZURE_SYSTEM,
        CONNECTION_NAME: alias,
        'Groups': '',
    }


def test_service_account_mapping():
    service = json.loads(service_principal_response())['value'][0]
    service_tuple = service_from_tuple(service, reader_roles)
    expected_response = _service_account_expected_response()

    lo = _map_service_account_response_to_laika_object(service_tuple, alias)

    assert expected.items() < lo.items()
    assert expected_response == lo


def service_from_tuple(roles, service):
    service = ServicePrincipal(roles, service, 'TEST-SUBSCRIPTION')
    return service


def _service_account_expected_response():
    return {
        'Created Date': '2021-04-24T02:02:59Z',
        'Description': None,
        'Display Name': 'Laika-Test-Service',
        'Email': '',
        'Id': 'a794c95b-48c5-4614-91f4-bb882884bd24',
        'Is Active': True,
        'Owner Id': 'TEST-SUBSCRIPTION',
        'Roles': 'CustomReaderRole',
        SOURCE_SYSTEM: AZURE_SYSTEM,
        CONNECTION_NAME: alias,
    }
