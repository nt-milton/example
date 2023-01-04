import json
from pathlib import Path

import pytest as pytest
from httmock import HTTMock, response, urlmatch

from integration.exceptions import ConnectionAlreadyExists
from integration.log_utils import connection_log
from integration.models import ConnectionAccount
from integration.sentry import implementation
from integration.sentry.tests.fake_api import (
    fake_sentry_api,
    fake_sentry_api_missing_credential,
    monitor_response,
    users_response,
)
from integration.tests import create_connection_account
from objects.models import LaikaObject
from user.tests import create_user

FAKE_API_AUTH_TOKEN = 'fake_api_auth_token'
USER = 'User'


def load_response(file_name):
    parent_path = Path(__file__).parent
    with open(parent_path / file_name, 'r') as file:
        return file.read()


@pytest.fixture
def connection_account():
    with fake_sentry_api():
        yield sentry_connection_account()


@pytest.fixture
def connection_account_all_projects():
    with fake_sentry_api():
        yield sentry_connection_account_all_projects()


@pytest.fixture
def connection_account_connect():
    with fake_sentry_api():
        yield sentry_connection_account_connect()


@pytest.fixture
def connection_account_error_response():
    with fake_sentry_api_missing_credential():
        yield sentry_connection_account()


@pytest.fixture
def failure_projects_counting():
    return {'count': 0}


@pytest.fixture
def failure_monitors_counting():
    return {'count': 0}


@pytest.mark.functional
def test_sentry_with_too_many_requests(
    connection_account, failure_projects_counting, failure_monitors_counting
):
    @urlmatch(netloc='sentry.io', path=r'/api/0/organizations/project_1/combined-rules')
    def monitors_too_many_requests(url, request):
        failure_monitors_counting['count'] = int(failure_monitors_counting['count']) + 1
        if int(failure_monitors_counting['count']) == 1:
            return response(
                status_code=429,
                headers={'Retry-After': 1},
                content='{"error": "too-many-requests"}',
            )
        return response(status_code=200, content=monitor_response('project_1'))

    with HTTMock(monitors_too_many_requests):
        implementation.run(connection_account)

    monitors = LaikaObject.objects.filter(
        connection_account=connection_account, object_type__display_name='Monitor'
    )
    assert connection_account.status == 'success'
    assert monitors.count() == 3


@pytest.mark.functional
def test_sentry_with_all_projects_selected_and_not_found_data(
    connection_account_all_projects,
):
    # Date range if not set then will be 18 months
    # Project 1: 18 events, fake_api will make 2 to be out of the date range
    # Project 2: 2 events, fake_api will leave both within the date range
    # Project 3: return 404 error to handle monitors with that error
    # So this will give us 16 events for project 1 and 2 for project 2

    connection_account_all_projects.integration.metadata['cursor_chunks'] = 15
    connection_account_all_projects.integration.metadata['delete'] = 'v2'
    run_and_assert_connection_account(connection_account_all_projects)


@pytest.mark.functional
def test_sentry_with_none_projects_selected(connection_account_connect):
    # Date range if not set then will be 18 months
    # Project 1: 18 events, fake_api will make 2 to be out of the date range
    # Project 2: 2 events, fake_api will leave both within the date range
    # Project 3: return 404 error to handle monitors with that error
    # So this will give us 16 events for project 1 and 2 for project 2
    with connection_log(connection_account_connect):
        run_and_assert_connection_account(connection_account_connect)


@pytest.mark.functional
def test_sentry_active_user_only(connection_account: ConnectionAccount) -> None:
    implementation.run(connection_account)

    @urlmatch(netloc='sentry.io', path=r'/api/0/')
    def disable_sentry_user(url, request):
        if 'organizations' in url.path:
            if 'users' in url.path:
                should_be_edited = True
                users_data = users_response()
                data_with_inactive_user = []
                for user in json.loads(users_data):
                    if user['user']['isActive'] and should_be_edited:
                        user['user']['isActive'] = False
                        should_be_edited = False
                    data_with_inactive_user.append(user)

                return response(status_code=200, content=data_with_inactive_user)

    with HTTMock(disable_sentry_user):
        implementation.run(connection_account)
    users = LaikaObject.objects.filter(
        connection_account=connection_account,
        object_type__display_name='Integration User',
        deleted_at__isnull=False,
    )
    assert connection_account.status == 'success'
    assert users.count() == 1


@pytest.mark.functional
def test_sentry_connect(
    connection_account_connect,
):
    implementation.connect(connection_account_connect)
    expected = [
        {
            'id': '2',
            'name': 'Laika organization',
            'slug': 'heylaika',
            'projects': [
                {
                    'id': '3',
                    'name': 'Project 1',
                    'slug': 'project_1',
                    'organization': 'heylaika',
                },
                {
                    'id': '3',
                    'name': 'Project 2',
                    'slug': 'project_2',
                    'organization': 'heylaika',
                },
                {
                    'id': '3',
                    'name': 'Project 3',
                    'slug': 'project_3',
                    'organization': 'heylaika',
                },
            ],
        }
    ]
    received = connection_account_connect.configuration_state.get('organizations')

    assert received == expected


def sentry_connection_account(**kwargs):
    connection_account = create_connection_account(
        'Sentry',
        authentication={},
        configuration_state={
            'credentials': {'authToken': FAKE_API_AUTH_TOKEN},
            'settings': {
                'selectedOrganizations': ['heylaika'],
                'selectedProjects': [
                    "{\"slug\":\"project_1\",\"name\":\"project_1\","
                    "\"organization\":\"project_1\"}",
                    "{\"slug\":\"project_2\",\"name\":\"project_2\","
                    "\"organization\":\"project_2\"}",
                    "{\"slug\":\"project_3\",\"name\":\"project_3\","
                    "\"organization\":\"project_3\"}",
                ],
            },
        },
        **kwargs
    )
    connection_account.integration.metadata['eventApi'] = 'monitor'
    return connection_account


def sentry_connection_account_connect(**kwargs):
    ca = sentry_connection_account(**kwargs)
    ca.configuration_state = {'credentials': {'authToken': FAKE_API_AUTH_TOKEN}}
    return ca


def sentry_connection_account_all_projects(**kwargs):
    ca = sentry_connection_account(**kwargs)
    ca.configuration_state = {
        'credentials': {'authToken': FAKE_API_AUTH_TOKEN},
        'settings': {
            'selectedOrganizations': ['heylaika'],
            'selectedProjects': [
                "{\"slug\":\"all\",\"name\":\"All projects Selected\","
                "\"organization\":\"heylaika\"}"
            ],
            'allProjectsSelected': True,
        },
    }
    return ca


def run_and_assert_connection_account(connection_account: ConnectionAccount) -> None:
    implementation.run(connection_account)

    monitors = LaikaObject.objects.filter(
        connection_account=connection_account, object_type__display_name='Monitor'
    )
    assert connection_account.status == 'success'
    assert monitors.count() == 1


@pytest.mark.functional
def test_raise_if_is_duplicate(connection_account):
    created_by = create_user(
        connection_account.organization, email='heylaika+test+vetty+ca@heylaika.com'
    )
    create_connection_account(
        'Sentry-2',
        authentication={},
        organization=connection_account.organization,
        integration=connection_account.integration,
        created_by=created_by,
        configuration_state={'credentials': {'authToken': FAKE_API_AUTH_TOKEN}},
    )
    with pytest.raises(ConnectionAlreadyExists):
        implementation.run(connection_account)
