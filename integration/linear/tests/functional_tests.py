import pytest
from httmock import HTTMock, response, urlmatch

from integration import linear
from integration.account import set_connection_account_number_of_records
from integration.error_codes import INSUFFICIENT_PERMISSIONS
from integration.exceptions import ConfigurationError
from integration.linear.implementation import N_RECORDS
from integration.linear.tests.fake_api import fake_linear_api, load_response
from integration.models import PENDING, ConnectionAccount
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import (
    create_error_catalogue,
    create_integration_alert,
    get_db_number_of_records,
)
from integration.views import oauth_callback
from objects.models import LaikaObject, LaikaObjectType
from objects.system_types import ACCOUNT, CHANGE_REQUEST, USER

LINEAR_SYSTEM = 'linear'


@pytest.fixture
def connection_account():
    with fake_linear_api():
        yield linear_connection_account()


@pytest.mark.functional
def test_linear_integration_callback(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, LINEAR_SYSTEM)
    assert connection_account.status == PENDING
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=USER.type
    )
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=ACCOUNT.type
    )
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=CHANGE_REQUEST.type
    )


@pytest.mark.functional
def test_linear_integration_with_not_admin_user(connection_account):
    integration = connection_account.integration
    catalogue = create_error_catalogue(
        '002', 'INSUFFICIENT_PERMISSIONS', 'IS NOT ADMIN', False
    )
    create_integration_alert(integration, catalogue, '001')

    @urlmatch(netloc='api.linear.app', path='/graphql')
    def user_info(url, request):
        query = "".join(request.body.decode("utf-8").split("\\n"))
        if 'viewer' in query:
            return response(
                status_code=200,
                content=dict(
                    data=dict(viewer=dict(admin=False, email='test@email.com'))
                ),
            )

    with HTTMock(user_info):
        request = create_request_for_callback(connection_account)
        oauth_callback(request, LINEAR_SYSTEM)
    ca = ConnectionAccount.objects.get(id=connection_account.id)
    assert ca.status == PENDING
    assert ca.error_code == INSUFFICIENT_PERMISSIONS


@pytest.mark.functional
def test_linear_integrate_account_number_of_records(connection_account):
    linear.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_linear_denial_of_consent_validation(connection_account):
    with pytest.raises(ConfigurationError):
        linear.callback(None, 'test-linear-callback', connection_account)


@pytest.mark.functional
def test_get_custom_field_options(connection_account):
    get_project_options = linear.get_custom_field_options("project", connection_account)
    expected_project = {
        'id': '6d579f59-0b8e-426f-9ef3-549d2a49afb4',
        'value': {'name': 'Second Project'},
    }
    assert get_project_options.options[0] == expected_project


@pytest.mark.functional
def test_linear_issues_with_invalid_format(connection_account):
    @urlmatch(netloc='api.linear.app', path='/graphql')
    def get_issues_with_bad_format(url, request):
        query = "".join(request.body.decode("utf-8").split("\\n"))
        if 'issues' in query:
            return response(
                status_code=200,
                content=load_response('raw_invalid_format_error_response.json'),
            )

    with HTTMock(get_issues_with_bad_format):
        linear.run(connection_account)
    change_requests = LaikaObject.objects.filter(
        connection_account=connection_account, object_type__type_name='change_request'
    ).count()

    assert change_requests == 0


@pytest.mark.functional
def test_linear_issues_with_none_response(connection_account):
    @urlmatch(netloc='api.linear.app', path='/graphql')
    def get_issues_with_none_value(url, request):
        query = "".join(request.body.decode("utf-8").split("\\n"))
        if 'issues' in query:
            return response(status_code=200, content='null')

    with HTTMock(get_issues_with_none_value):
        linear.run(connection_account)
    change_requests = LaikaObject.objects.filter(
        connection_account=connection_account, object_type__type_name='change_request'
    ).count()

    assert change_requests == 0


def linear_connection_account(**kwargs):
    connection_account = create_connection_account(
        'Linear',
        authentication={
            "access_token": "access_token",
            "token_type": "bearer",
            "expires_in": 3600,
            "scope": ["read"],
            "data": {
                "id": "7ec55b90-dd4f-45c0-ae2b-3ad78bf63c1e",
                "name": "Dev Team",
                "email": "dev@heylaika.com",
            },
        },
        configuration_state={
            'settings': {'projects': ['6d579f59-0b8e-426f-9ef3-549d2a49afb4']}
        },
        **kwargs
    )
    return connection_account


@pytest.mark.functional
def test_get_selected_projects(connection_account):
    settings = {'projects': ['All Projects Selected']}
    connection_account.configuration_state['settings'] = settings
    linear.run(connection_account)
    assert len(connection_account.settings['projects']) > 1
