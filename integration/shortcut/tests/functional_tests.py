from pathlib import Path

import pytest
from httmock import HTTMock, response, urlmatch

from integration import error_codes
from integration.account import set_connection_account_number_of_records
from integration.exceptions import ConfigurationError, TimeoutException
from integration.models import ConnectionAccount
from integration.shortcut import implementation
from integration.shortcut.implementation import N_RECORDS
from integration.tests import create_connection_account
from integration.tests.factory import get_db_number_of_records
from laika.tests import mock_responses

FAKE_API_KEY = 'fake_api_key'
RAW_USERS_RESPONSE_JSON = 'raw_users_response.json'
RAW_CHANGE_REQUEST_RESPONSE_JSON = 'raw_change_request_response.json'
RAW_WORKFLOW_RESPONSE_JSON = 'raw_workflow_states_response.json'


def load_response(file_name):
    parent_path = Path(__file__).parent
    with open(parent_path / file_name, 'r') as file:
        return file.read()


def _get_responses():
    return [
        load_response(RAW_WORKFLOW_RESPONSE_JSON),
        load_response('raw_epic_response.json'),
        load_response('raw_member_info_response.json'),
        load_response(RAW_WORKFLOW_RESPONSE_JSON),
    ]


@urlmatch(netloc=r'api.app.shortcut.com', path='/api/v3/search/stories')
def maximum_results_exceeded(url, request):
    return response(status_code=400, content=' {"error": "maximum-results-exceeded"}')


@pytest.fixture
def connection_account():
    # Omit validation for testing purpose, sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    responses = _get_responses() + [
        load_response('raw_stories.json'),
        load_response('raw_story_history_response.json'),
        load_response(RAW_USERS_RESPONSE_JSON),
        load_response(RAW_CHANGE_REQUEST_RESPONSE_JSON),
    ]
    with mock_responses(responses):
        yield shortcut_connection_account()


@pytest.fixture
def connection_account_maximum_results_exceeded():
    # Omit validation for testing purpose, sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    responses = _get_responses() + [
        load_response(RAW_USERS_RESPONSE_JSON),
        load_response(RAW_CHANGE_REQUEST_RESPONSE_JSON),
    ]
    with mock_responses(responses):
        yield shortcut_connection_account()


@pytest.fixture
def connection_account_timeout_error():
    # Omit validation for testing purpose, sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    responses = [
        load_response('raw_epic_response.json'),
        load_response('raw_member_info_response.json'),
        load_response(RAW_WORKFLOW_RESPONSE_JSON),
        load_response('raw_stories.json'),
        load_response('raw_story_history_response.json'),
        load_response(RAW_USERS_RESPONSE_JSON),
        load_response(RAW_CHANGE_REQUEST_RESPONSE_JSON),
    ]
    with mock_responses(responses):
        yield shortcut_connection_account()


@pytest.fixture
def connection_account_for_user_integration():
    responses = [load_response(RAW_USERS_RESPONSE_JSON)]
    with mock_responses(responses):
        yield shortcut_connection_account()


@pytest.fixture
def connection_account_for_change_request_integration():
    responses = [load_response(RAW_CHANGE_REQUEST_RESPONSE_JSON)]
    with mock_responses(responses):
        yield shortcut_connection_account()


@pytest.mark.functional
def test_shortcut_integrate_account_number_of_records(connection_account):
    implementation.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_shortcut_maximum_results_exceeded_workflows(
    connection_account_maximum_results_exceeded,
):
    with HTTMock(maximum_results_exceeded):
        implementation.run(connection_account_maximum_results_exceeded)

        assert connection_account_maximum_results_exceeded.status == 'success'


@pytest.mark.functional
def test_shortcut_maximum_results_exceeded_projects(
    connection_account_maximum_results_exceeded,
):
    connection_account_maximum_results_exceeded.settings['workflows'] = []
    connection_account_maximum_results_exceeded.settings['projects'] = ['1234']

    with HTTMock(maximum_results_exceeded):
        implementation.run(connection_account_maximum_results_exceeded)

        assert connection_account_maximum_results_exceeded.status == 'success'


@pytest.mark.functional
def test_shortcut_integration_connect(connection_account):
    implementation.connect(connection_account)

    assert connection_account.status == 'pending'
    assert connection_account.authentication == {
        'prefetch_workflow': [{'id': '123', 'value': {'name': 'test'}}]
    }


@pytest.mark.functional
def test_shortcut_integration_account_is_active(
    connection_account: ConnectionAccount,
) -> None:
    implementation.run(connection_account)
    is_active_account = (
        connection_account.laika_objects.filter(
            object_type__type_name='account', is_manually_created=False
        )
        .first()
        .data['Is Active']
    )
    assert is_active_account


@pytest.mark.functional
def test_shortcut_integration_account_is_inactive(
    connection_account: ConnectionAccount,
) -> None:
    implementation.run(connection_account)

    @urlmatch(netloc=r'api.app.shortcut.com', path='/api/v3/projects')
    def without_projects_response(url, request):
        return response(status_code=400, content='{"error": "No projects in response"}')

    with HTTMock(without_projects_response):
        with pytest.raises(ConfigurationError):
            implementation.run(connection_account)

    is_active_account = (
        connection_account.laika_objects.filter(
            object_type__type_name='account', is_manually_created=False
        )
        .first()
        .data['Is Active']
    )
    assert not is_active_account


def shortcut_connection_account(**kwargs):
    return create_connection_account(
        'Shortcut',
        authentication={},
        configuration_state={
            'credentials': {
                'apiKey': FAKE_API_KEY,
            },
            'settings': {'workflows': ["123"]},
        },
        **kwargs
    )


@pytest.fixture
def function_call_counting():
    return {'count': 0}


@pytest.mark.functional
def test_shortcut_timeout_exception_error_result(
    connection_account, function_call_counting
):
    @urlmatch(netloc=r'api.app.shortcut.com', path='/api/v3/search/stories')
    def call_with_timeout_error(url, request):
        function_call_counting['count'] = int(function_call_counting['count']) + 1
        return response(status_code=408, content=' {"error": "timeout error"}')

    with HTTMock(call_with_timeout_error):
        with pytest.raises(TimeoutException):
            implementation.run(connection_account)

    assert connection_account.result.get('error_response') == 'Timeout Error.'
    assert connection_account.status == 'error'
    assert function_call_counting.get('count') == 3
    assert connection_account.error_code == error_codes.CONNECTION_TIMEOUT


@pytest.mark.functional
def test_shortcut_timeout_exception_success_result(
    connection_account_timeout_error, function_call_counting
):
    @urlmatch(netloc=r'api.app.shortcut.com', path='/api/v3/projects')
    def call_with_timeout_error(url, request):
        function_call_counting['count'] = int(function_call_counting['count']) + 1
        if int(function_call_counting['count']) == 1:
            return response(status_code=408, content=' {"error": "timeout error"}')
        return response(
            status_code=200, content=load_response('raw_projects_response.json')
        )

    with HTTMock(call_with_timeout_error):
        implementation.run(connection_account_timeout_error)

    assert connection_account_timeout_error.status == 'success'
    assert function_call_counting.get('count') == 2
    assert connection_account_timeout_error.error_code == error_codes.NONE
