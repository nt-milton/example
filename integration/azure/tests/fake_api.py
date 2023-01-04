from pathlib import Path

from httmock import HTTMock, urlmatch

TEST_DIR = Path(__file__).parent


def fake_azure_api():
    return HTTMock(_fake_auth_response, _fake_microsoft_api, _fake_management_api)


def fake_azure_api_missing_credential():
    return HTTMock(_fake_auth_response_without_client_id)


def fake_azure_api_permission_denied():
    return HTTMock(_fake_permission_denied_error())


@urlmatch(netloc='graph.microsoft.com')
def _fake_microsoft_api(url, request):
    if 'users' in url.path:
        if 'memberOf' in url.path:
            if 'microsoft.graph.group' in url.path:
                user_group_response()
            return groups_roles_response()
        return users_response()
    if 'organization' in url.path:
        return organization_response()
    if 'applications' in url.path:
        return application_credentials_response()
    if 'servicePrincipals' in url.path:
        return service_principal_response()
    raise ValueError('Unexpected operation for microsoft azure fake api')


@urlmatch(netloc='management.azure.com')
def _fake_management_api(url, request):
    if 'roleAssignments' in url.path:
        return subscription_roles()

    if 'roleDefinitions' in url.path:
        return role_definitions()

    raise ValueError('Unexpected operation for microsoft management azure fake api')


def subscription_roles():
    path = TEST_DIR / 'raw_user_subscription_role_response.json'
    return open(path, 'r').read()


def role_definitions():
    path = TEST_DIR / 'raw_role_definitions_response.json'
    return open(path, 'r').read()


def users_response():
    path = TEST_DIR / 'raw_users_response.json'
    return open(path, 'r').read()


def organization_response():
    path = TEST_DIR / 'raw_organization_response.json'
    return open(path, 'r').read()


def groups_roles_response():
    path = TEST_DIR / 'raw_groups_roles_response.json'
    return open(path, 'r').read()


def application_credentials_response():
    path = TEST_DIR / 'raw_application_credentials_response.json'
    return open(path, 'r').read()


def service_principal_response():
    path = TEST_DIR / 'raw_service_principal_response.json'
    return open(path, 'r').read()


def user_group_response():
    path = TEST_DIR / 'raw_user_groups_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='login.microsoftonline.com')
def _fake_auth_response(url, request):
    path = TEST_DIR / 'raw_token_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='login.microsoftonline.com')
def _fake_auth_response_without_client_id(url, request):
    path = TEST_DIR / 'raw_error_response.json'
    return open(path, 'r').read()


def _fake_permission_denied_error():
    path = TEST_DIR / 'raw_error_response.json'
    return open(path, 'r').read()
