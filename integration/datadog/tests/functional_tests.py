from pathlib import Path

import pytest
from httmock import HTTMock, response, urlmatch

from integration.account import set_connection_account_number_of_records
from integration.datadog.implementation import (
    N_RECORDS,
    connect,
    raise_if_duplicate,
    run,
    run_by_lo_types,
)
from integration.datadog.rest_client import MAX_EMPTY_MONTHS
from integration.encryption_utils import encrypt_value
from integration.error_codes import USER_INPUT_ERROR
from integration.exceptions import ConfigurationError, ConnectionAlreadyExists
from integration.models import ConnectionAccount, ErrorCatalogue
from integration.tests import create_connection_account
from integration.tests.factory import create_error_catalogue, get_db_number_of_records
from laika.tests import mock_responses
from laika.tests.utils import mock_responses_with_status
from objects.models import LaikaObject
from objects.system_types import (
    ACCOUNT,
    EVENT,
    MONITOR,
    USER,
    resolve_laika_object_type,
)

FAKE_API_KEY = 'fake_api_key'
FAKE_APPLICATION_KEY = 'fake_application_key'


def load_response(file_name):
    parent_path = Path(__file__).parent
    with open(parent_path / file_name, 'r') as file:
        return file.read()


@pytest.fixture
def monitor_response():
    yield load_response('raw_monitor_response.json')


@pytest.fixture
def events_response():
    yield load_response('raw_events_response.json')


@pytest.fixture
def empty_events_response():
    yield load_response('raw_empty_events_response.json')


@pytest.fixture
def users_response():
    yield load_response('raw_users_response.json')


@pytest.fixture
def users_bad_request_response():
    yield load_response('raw_users_bad_request_response.json')


@pytest.fixture
def managed_organizations_response():
    yield load_response('raw_managed_organizations_response.json')


@pytest.fixture
def service_accounts_response():
    yield load_response('raw_service_accounts_response.json')


@pytest.fixture
def monitor_forbidden_error_response():
    yield load_response('raw_monitors_error_response.json')


@pytest.fixture
def connection_account(
    monitor_response,
    events_response,
    empty_events_response,
    users_response,
    managed_organizations_response,
    service_accounts_response,
):
    responses = [
        managed_organizations_response,
        service_accounts_response,
        users_response,
        monitor_response,
        events_response,
    ]
    responses.extend([empty_events_response for _ in range(0, MAX_EMPTY_MONTHS + 1)])
    with mock_responses(responses):
        yield datadog_connection_account()


@pytest.fixture
def connection_account_users_bad_request(
    monitor_response,
    events_response,
    empty_events_response,
    users_bad_request_response,
    managed_organizations_response,
    service_accounts_response,
):
    monitors = response(status_code=200, content=monitor_response)
    managed_orgs = response(status_code=200, content=managed_organizations_response)
    users = response(status_code=403, content=users_bad_request_response)
    service_accounts = response(status_code=200, content=service_accounts_response)
    responses = [monitors, managed_orgs, users, service_accounts]
    with mock_responses_with_status(responses):
        yield datadog_connection_account()


@pytest.fixture
def connection_account_for_monitor_integration(
    monitor_response,
    users_response,
    managed_organizations_response,
    service_accounts_response,
):
    responses = [
        monitor_response,
        managed_organizations_response,
        service_accounts_response,
        users_response,
    ]
    with mock_responses(responses):
        yield datadog_connection_account()


@pytest.mark.functional
def test_datadog_integration_filter(connection_account):
    lo_type_monitor = resolve_laika_object_type(
        connection_account.organization, MONITOR
    )
    lo_type_event = resolve_laika_object_type(connection_account.organization, EVENT)
    run(connection_account)
    assert not LaikaObject.objects.filter(object_type=lo_type_monitor).exists()
    assert not LaikaObject.objects.filter(object_type=lo_type_event).exists()


@pytest.mark.functional
def test_datadog_run_by_lo_types_with_lo_type(connection_account):
    lo_type_monitor = resolve_laika_object_type(
        connection_account.organization, MONITOR
    )
    resolve_laika_object_type(connection_account.organization, EVENT)
    run_by_lo_types(connection_account, ['testing'])
    assert not LaikaObject.objects.filter(object_type=lo_type_monitor).exists()


@pytest.mark.functional
def test_datadog_run_by_lo_types_without_lo_types(
    connection_account_for_monitor_integration,
):
    lo_type = resolve_laika_object_type(
        connection_account_for_monitor_integration.organization, MONITOR
    )
    connection_account_for_monitor_integration.configuration_state['settings'][
        'datasets'
    ] = [MONITOR.type]
    run_by_lo_types(connection_account_for_monitor_integration, [])
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@pytest.mark.functional
def test_datadog_integration_create_monitor_laika_objects(
    connection_account_for_monitor_integration,
):
    lo_type = resolve_laika_object_type(
        connection_account_for_monitor_integration.organization, MONITOR
    )
    connection_account_for_monitor_integration.configuration_state['settings'][
        'datasets'
    ] = [MONITOR.type]
    run(connection_account_for_monitor_integration)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@pytest.mark.functional
def test_datadog_run_with_error_in_monitors_response(
    connection_account_for_monitor_integration, monitor_forbidden_error_response
):
    @urlmatch(
        netloc=r'(api.datadoghq.com|api.datadoghq.eu|'
        r'api.us3.datadoghq.com|api.ddog-gov.com)',
        path='/api/v1/monitor',
    )
    def invalid_monitors(url, request):
        return response(status_code=403, content=monitor_forbidden_error_response)

    connection_account_for_monitor_integration.configuration_state['settings'][
        'datasets'
    ] = [MONITOR.type]
    with HTTMock(invalid_monitors):
        with pytest.raises(ConfigurationError) as exinfo:
            run(connection_account_for_monitor_integration)

    assert str(exinfo.value) == 'The connection does not have admin privileges.'


@pytest.mark.functional
def test_datadog_integration_create_account_laika_objects(connection_account):
    lo_type = resolve_laika_object_type(connection_account.organization, ACCOUNT)
    run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@pytest.mark.functional
def test_datadog_integrate_account_number_of_records(connection_account):
    run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


def datadog_connection_account(**kwargs):
    return create_connection_account(
        'Datadog',
        authentication={},
        configuration_state={
            'credentials': {
                'apiKey': encrypt_value(FAKE_API_KEY),
                'programKey': encrypt_value(FAKE_APPLICATION_KEY),
            },
            'settings': {'datasets': []},
        },
        **kwargs
    )


@pytest.mark.functional
def test_datadog_integration_upsert_runs_successfully(
    connection_account_for_monitor_integration,
):
    connection_account_for_monitor_integration.configuration_state['settings'][
        'datasets'
    ] = [MONITOR.type]
    run(connection_account_for_monitor_integration)
    assert (
        'last_successful_run'
        in connection_account_for_monitor_integration.configuration_state
    )
    assert connection_account_for_monitor_integration.status == 'success'


@pytest.mark.functional
def test_datadog_success_connection(connection_account):
    @urlmatch(netloc=r'api.datadoghq.com', path='/api/v1/monitor')
    def valid_monitor(url, request):
        return response(status_code=200, content={'message': 'fake content'})

    with HTTMock(valid_monitor):
        connect(connection_account=connection_account)

    assert (
        connection_account.authentication.get('site') == 'https://api.datadoghq.com/api'
    )


@pytest.mark.functional
def test_datadog_success_connection_on_another_site(
    connection_account, monitor_forbidden_error_response
):
    @urlmatch(netloc=r'api.datadoghq.com', path='/api/v1/monitor')
    def invalid_monitor(url, request):
        return response(status_code=403, content=monitor_forbidden_error_response)

    @urlmatch(netloc=r'api.datadoghq.eu', path='/api/v1/monitor')
    def valid_monitor(url, request):
        return response(status_code=200, content={'message': 'fake content'})

    with HTTMock(invalid_monitor, valid_monitor):
        connect(connection_account=connection_account)

    assert (
        connection_account.authentication.get('site') == 'https://api.datadoghq.eu/api'
    )


@pytest.mark.functional
def test_datadog_fail_connection(connection_account, monitor_forbidden_error_response):
    @urlmatch(
        netloc=r'(api.datadoghq.com|api.datadoghq.eu|'
        r'api.us3.datadoghq.com|api.ddog-gov.com)',
        path='/api/v1/monitor',
    )
    def invalid_monitors(url, request):
        return response(status_code=403, content=monitor_forbidden_error_response)

    create_error_catalogue(USER_INPUT_ERROR)
    with HTTMock(invalid_monitors):
        with pytest.raises(ConfigurationError):
            connect(connection_account=connection_account)

    assert connection_account.authentication.get('site') is None


@pytest.mark.functional
def test_datadog_fail_connection_due_provider_server_error(connection_account):
    ErrorCatalogue.objects.create(
        code=USER_INPUT_ERROR,
        default_wizard_message='Error with the site',
        default_message='Error getting site',
    )

    @urlmatch(
        netloc=r'(api.datadoghq.com|api.datadoghq.eu|'
        r'api.us3.datadoghq.com|api.ddog-gov.com)',
        path='/api/v1/monitor',
    )
    def invalid_monitors(url, request):
        return response(status_code=500, content={"errors": "provider error"})

    with HTTMock(invalid_monitors):
        with pytest.raises(ConfigurationError):
            connect(connection_account=connection_account)

    assert connection_account.authentication.get('site') is None


@pytest.mark.functional
def test_should_raise_connection_already_exists(connection_account: ConnectionAccount):
    # Existing connection should be success or in error state
    connection_account.status = 'success'
    connection_account.save()

    # Same apiKey, programKey, organization
    duplicated_connection = ConnectionAccount.objects.create(
        alias='Duplicate Datadog',
        authentication={},
        configuration_state={
            'credentials': {
                'apiKey': FAKE_API_KEY,
                'programKey': FAKE_APPLICATION_KEY,
            },
            'settings': {'datasets': ['monitor']},
        },
        integration=connection_account.integration,
        organization=connection_account.organization,
    )
    with pytest.raises(ConnectionAlreadyExists):
        raise_if_duplicate(duplicated_connection)


@pytest.mark.functional
def test_error_getting_users(connection_account_users_bad_request):
    user_lo_type = resolve_laika_object_type(
        connection_account_users_bad_request.organization, USER
    )
    monitor = MONITOR.type
    event = EVENT.type
    connection_account_users_bad_request.configuration_state['settings']['datasets'] = [
        monitor,
        event,
    ]

    run(connection_account=connection_account_users_bad_request)

    # Not users
    assert not LaikaObject.objects.filter(object_type=user_lo_type).exists()
