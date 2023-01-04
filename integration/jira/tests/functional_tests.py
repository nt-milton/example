import json
from unittest.mock import patch

import pytest

from integration import jira
from integration.account import set_connection_account_number_of_records
from integration.error_codes import INSUFFICIENT_PERMISSIONS
from integration.exceptions import ConfigurationError
from integration.jira.constants import INSUFFICIENT_ADMINISTRATOR_PERMISSIONS
from integration.jira.implementation import JIRA_SYSTEM, N_RECORDS, run_by_lo_types
from integration.jira.tests.fake_api import (
    fake_jira_api,
    fake_jira_api_expired_token,
    fake_jira_api_for_validation,
    load_response,
)
from integration.models import PENDING, ConnectionAccount
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import (
    create_error_catalogue,
    create_integration_alert,
    get_db_number_of_records,
)
from integration.views import oauth_callback
from objects.models import LaikaObject, LaikaObjectType
from objects.system_types import (
    ACCOUNT,
    CHANGE_REQUEST,
    USER,
    resolve_laika_object_type,
)


@pytest.fixture
def connection_account():
    with fake_jira_api():
        yield jira_connection_account()


@pytest.fixture
def connection_account_for_validation():
    with fake_jira_api_for_validation():
        yield jira_connection_account()


@pytest.fixture
def connection_account_expired_token():
    with fake_jira_api_expired_token():
        yield jira_connection_account()


@pytest.mark.functional
def test_jira_denial_of_consent_validation(connection_account_for_validation):
    with pytest.raises(ConfigurationError):
        jira.callback(None, 'test-jira-callback', connection_account_for_validation)


@pytest.mark.functional
def test_jira_validations(connection_account_for_validation):
    error = create_error_catalogue(INSUFFICIENT_PERMISSIONS)
    integration = connection_account_for_validation.integration
    create_integration_alert(integration, error, INSUFFICIENT_ADMINISTRATOR_PERMISSIONS)
    with pytest.raises(ConfigurationError):
        jira.callback('code', 'test-jira-callback', connection_account_for_validation)


@pytest.mark.functional
def test_jira_run_by_lo_types_with_change_request(connection_account):
    run_by_lo_types(connection_account, [])
    assert LaikaObject.objects.filter(
        object_type__type_name=CHANGE_REQUEST.type
    ).exists()


@pytest.mark.functional
def test_jira_run_by_lo_types_without_user(connection_account):
    run_by_lo_types(connection_account, ['testing_type'])
    assert not LaikaObject.objects.filter(object_type__type_name=USER.type).exists()


@pytest.mark.functional
def test_jira_integration_create_laika_objects_expired_token(
    connection_account_expired_token,
):
    jira.run(connection_account_expired_token)

    assert LaikaObject.objects.filter(
        object_type__type_name=CHANGE_REQUEST.type
    ).exists()


@pytest.mark.functional
def test_jira_integration_create_account_laika_objects_expired_token(
    connection_account_expired_token,
):
    jira.run(connection_account_expired_token)
    assert LaikaObject.objects.filter(object_type__type_name=ACCOUNT.type).exists()


@pytest.mark.functional
def test_jira_integration_create_change_request_laika_objects_expired_token(
    connection_account_expired_token,
):
    jira.run(connection_account_expired_token)
    assert LaikaObject.objects.filter(
        object_type__type_name=CHANGE_REQUEST.type
    ).exists()


@pytest.mark.functional
def test_jira_integration_create_user_laika_objects(connection_account):
    connection_account.authentication[
        'scope'
    ] = 'read:jira-user manage:jira-configuration'
    lo_type = resolve_laika_object_type(connection_account.organization, USER)
    jira.run(connection_account)
    assert LaikaObject.objects.filter(object_type=lo_type).exists()


@pytest.mark.functional
def test_jira_integrate_account_number_of_records(connection_account):
    jira.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_jira_integration_callback(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, JIRA_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    expected_prefetch = {
        'id': 'TR-10020-TRANSFORMERS',
        'value': {'name': 'TRANSFORMERS', 'projectType': 'software'},
    }
    prefetch = connection_account.authentication['prefetch_project'][5]
    assert prefetch == expected_prefetch
    assert connection_account.status == PENDING
    assert LaikaObjectType.objects.get(
        organization=connection_account.organization, type_name=CHANGE_REQUEST.type
    )


@pytest.mark.functional
def test_jira_integration_callback_expired_token(connection_account_expired_token):
    request = create_request_for_callback(connection_account_expired_token)
    oauth_callback(request, JIRA_SYSTEM)
    connection_account_expired_token = ConnectionAccount.objects.get(
        control=connection_account_expired_token.control
    )
    assert connection_account_expired_token.status == PENDING
    assert LaikaObjectType.objects.get(
        organization=connection_account_expired_token.organization,
        type_name=CHANGE_REQUEST.type,
    )


def jira_connection_account(**kwargs):
    return create_connection_account(
        'Jira',
        authentication=dict(
            refresh_token='MyToken',
            resources=[{'id': 'heylaika'}],
            scope="manage:jira-configuration",
        ),
        configuration_state=dict(settings=dict(projects=['TR-10020-Autobots'])),
        **kwargs
    )


@pytest.mark.functional
def test_get_custom_field_options(connection_account):
    get_project_options = jira.get_custom_field_options("project", connection_account)
    expected_project = {
        'id': 'CON-10008-Concierge',
        'value': {'name': 'Concierge', 'projectType': 'software'},
    }
    assert get_project_options.options[0] == expected_project


@pytest.mark.functional
def test_raise_error_for_unknown_field(connection_account):
    with pytest.raises(NotImplementedError):
        jira.get_custom_field_options("organization", connection_account)


@pytest.mark.functional
def test_jira_integration_with_one_project_settings(connection_account):
    settings = {'projects': ['TR-10020-Autobots']}
    connection_account.configuration_state['settings'] = settings
    mock_func = 'integration.jira.implementation.get_paginated_response_by_api_method'

    with patch(mock_func) as mock_api_method:
        jira.run(connection_account)
        mock_api_method.assert_called()


@pytest.mark.functional
def test_error_refreshing_token_is_persisted(connection_account):
    mock_func = 'integration.jira.implementation.delete_if_close_account'

    error = ConfigurationError.insufficient_permission()
    with patch(mock_func) as mock_api_method:
        with pytest.raises(ConfigurationError):
            mock_api_method.side_effect = error
            jira.run(connection_account)
            mock_api_method.assert_called()
    connection_account.refresh_from_db()
    assert connection_account.status == 'error'


@pytest.mark.functional
def test_jira_ticket_transitions(expected_transitions):
    ticket_response = json.loads(load_response('raw_tickets_response.json'))
    transitions_response = jira.implementation.get_transitions_from_ticket(
        ticket_response['issues'][0]
    )

    assert transitions_response == expected_transitions


@pytest.mark.functional
def test_get_selected_projects(connection_account):
    settings = {'projects': ['All Projects Selected']}
    connection_account.configuration_state['settings'] = settings
    jira.run(connection_account)
    assert len(connection_account.settings['projects']) > 1


@pytest.fixture
def expected_transitions():
    first_author = 'Ronald Zúñiga'
    second_author = 'Kenneth Diaz'
    status = 'status'
    in_progress = 'In Progress'
    return [
        {
            'author': first_author,
            'field': 'created',
            'date': '2020-07-09T16:28:14.497-0400',
        },
        {
            'author': first_author,
            'field': 'assignee',
            'date': '2020-09-02T16:34:21.183-0400',
            'before': 'None',
            'after': second_author,
        },
        {
            'author': second_author,
            'field': status,
            'date': '2020-10-15T14:35:55.589-0400',
            'before': 'Backlog',
            'after': in_progress,
        },
        {
            'author': 'Sébastien Theunissen',
            'field': status,
            'date': '2020-10-20T09:47:51.397-0400',
            'before': in_progress,
            'after': 'Backlog',
        },
        {
            'author': second_author,
            'field': status,
            'date': '2020-11-05T09:30:26.645-0500',
            'before': 'Backlog',
            'after': in_progress,
        },
        {
            'author': first_author,
            'field': status,
            'date': '2020-11-11T09:45:18.624-0500',
            'before': in_progress,
            'after': 'Blocked',
        },
    ]
