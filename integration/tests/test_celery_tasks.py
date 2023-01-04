from datetime import datetime, timedelta
from typing import Union
from unittest.mock import patch

import pytest
from django.utils import timezone as dj_tz

from integration.constants import SYNC
from integration.error_codes import (
    CONNECTION_TIMEOUT,
    DENIAL_OF_CONSENT,
    EXPIRED_TOKEN,
    INSUFFICIENT_PERMISSIONS,
    NONE,
    PROVIDER_SERVER_ERROR,
)
from integration.exceptions import ConfigurationError
from integration.google.tests.fake_api import fake_google_workspace_api
from integration.google.tests.functional_tests import (
    google_workspace_connection_account,
)
from integration.microsoft import implementation
from integration.microsoft.tests.fake_api import fake_microsoft_api
from integration.models import (
    ALREADY_EXISTS,
    ERROR,
    SUCCESS,
    ConnectionAccount,
    Integration,
)
from integration.tasks import (
    execute_connection_accounts,
    reconcile_sync_connections,
    run_integration,
    run_integration_on_test_mode,
    scale_simulator,
    update_connection_accounts_to_expired_token,
    update_integrations,
)
from integration.test_mode import test_state
from integration.tests.factory import create_connection_account, create_integration
from objects.models import LaikaObject
from objects.tests.factory import create_object_type
from organization.models import ACTIVE, Organization
from organization.tests import create_organization
from user.models import User
from user.tests import create_user

INTEGRATION_DELAY = 'integration.tasks.run_integration.delay'

UPDATED_CONNECTIONS = 'Updated connections'

TIMEZONE_NOW = 'django.utils.timezone.now'


def _create_connection_laika_objects(connection: ConnectionAccount):
    object_type = create_object_type(
        organization=connection.organization,
        display_name='Integration User',
        type_name='user',
        color='accentRed',
        display_index=1,
    )
    laika_objects = []
    for idx in range(2):
        lo = LaikaObject(
            object_type=object_type,
            connection_account=connection,
            data={'email': f'test_{idx}@heylaika.com'},
        )
        laika_objects.append(lo)
    LaikaObject.objects.bulk_create(laika_objects)


@pytest.fixture
def connection_account():
    with fake_google_workspace_api():
        connection = google_workspace_connection_account(status=SUCCESS)
        _create_connection_laika_objects(connection=connection)
        yield connection


@pytest.mark.functional()
def test_update_integrations_with_errors(mock_renew_token):
    integration = create_integration('microsoft_365')
    two_days_ago = datetime.now() - timedelta(days=2)

    with fake_microsoft_api():
        with patch(TIMEZONE_NOW) as mocked_now:
            mocked_now.return_value = two_days_ago
            create_connection_account_with_errors(integration)

            def omit_duplicate(ca):
                # Don't require an implementation
                pass

            implementation.raise_if_duplicate = omit_duplicate

            update_integrations()
            assert (
                ConnectionAccount.objects.filter(
                    status=SUCCESS, error_code=NONE
                ).count()
                == 5
            )


@pytest.mark.functional()
def test_run_integration_in_test_mode(connection_account, caplog):
    connection_account.authentication['installations'] = [
        {
            'login': 'heylaika',
            'access_token': 'ghs_FAKETOKEN1',
            'installation_id': 20867660,
        },
        {
            'login': 'autobots',
            'access_token': 'ghs_FAKETOKEN2',
            'installation_id': 21227133,
        },
    ]
    connection_account.save()
    connection_id = connection_account.id

    with patch.object(LaikaObject.objects, 'update_or_create') as store_mck, patch(
        'laika.aws.s3.s3_client.put_object'
    ) as put_mock:
        put_mock.return_value = {'ETag': 'ETagValue'}

        def omit_duplicate(ca):
            # Don't require an implementation
            pass

        implementation.raise_if_duplicate = omit_duplicate
        result = run_integration_on_test_mode(connection_id=connection_id)
        assert result == {'ETag': 'ETagValue'}
        put_mock.assert_called_once()
        # This validates the task don't update any existing LO
        store_mck.assert_not_called()

    assert test_state.in_test_mode is False
    assert test_state.connection_id is None
    assert test_state.responses == []
    all_laika_objects = LaikaObject.objects.filter(
        connection_account=connection_account
    )
    assert all_laika_objects.count() == 2
    lo_emails = list(all_laika_objects.all().values_list('data__email', flat=True))
    for idx, email in enumerate(lo_emails):
        assert f'test_{idx}@heylaika.com' in lo_emails
    assert 'Not running update_laika_objects due in testing mode' in caplog.text
    assert f'Running connection {connection_id} in testing mode' in caplog.text


@pytest.mark.functional()
def test_run_failed_integration_in_test_mode(connection_account, caplog):
    connection_account.authentication['installations'] = [
        {
            'login': 'heylaika',
            'access_token': 'ghs_FAKETOKEN1',
            'installation_id': 20867660,
        },
        {
            'login': 'autobots',
            'access_token': 'ghs_FAKETOKEN2',
            'installation_id': 21227133,
        },
    ]
    connection_account.save()
    connection_id = connection_account.id

    with patch.object(LaikaObject.objects, 'update_or_create') as store_mck, patch(
        'laika.aws.s3.s3_client.put_object'
    ) as put_mock, patch(
        'integration.github_apps.implementation.integrate_users'
    ) as run_mck:
        put_mock.return_value = {'ETag': 'ETagValue'}
        run_mck.side_effect = ConfigurationError.provider_server_error(
            {'message': 'error'}
        )

        def omit_duplicate(ca):
            # Don't require an implementation
            pass

        implementation.raise_if_duplicate = omit_duplicate
        result = run_integration_on_test_mode(connection_id=connection_id)
        assert result == {'ETag': 'ETagValue'}
        put_mock.assert_called_once()
        # This validates the task don't update any existing LO
        store_mck.assert_not_called()

    assert test_state.in_test_mode is False
    assert test_state.connection_id is None
    assert test_state.responses == []

    assert 'Not running update_laika_objects due in testing mode' in caplog.text
    assert f'Running connection {connection_id} in testing mode' in caplog.text


@pytest.mark.functional()
def test_run_integration_in_test_mode_while_sync(connection_account, caplog):
    connection_account.status = 'sync'
    connection_account.save()
    error_message = (
        "Connection account can't be executed on testing mode due is on SYNC status"
    )

    result = run_integration_on_test_mode(connection_id=connection_account.id)
    assert {
        'error': (
            'Error running integration with id '
            f'{connection_account.id} on Test mode. '
            f'Error: {error_message}'
        )
    } == result
    assert test_state.in_test_mode is False
    assert test_state.connection_id is None
    assert test_state.responses == []

    assert error_message in caplog.text


@pytest.mark.functional()
@patch('integration.google.run', return_value=None)
def test_run_integration_on_celery_worker(run_mck):
    organization = create_organization(name='organization', state=ACTIVE)
    created_by = create_user(organization, email='heylaika@heylaika.com')

    connection_1 = create_connection_account(
        'google_workspace',
        status=SUCCESS,
        created_by=created_by,
        organization=organization,
    )

    result = run_integration(connection_1.id, False)

    run_mck.assert_called_with(connection_1)
    assert 'connection_id' in result
    assert 'total_time' in result


@pytest.mark.functional()
@patch('integration.google.run', return_value=None)
def test_reconcile_on_celery_worker(run_mck):
    active_metadata = {
        'celery@b8ebdae306b8': [
            {'id': 'task-000', 'type': 'another_app.tasks.dummy_task'}
        ],
        'celery@2eede3e1413b': [
            {'id': 'task-123', 'type': 'integration.tasks.dummy_task'}
        ],
    }
    connection_1 = create_connection_account(
        'google_workspace', status=SYNC, updated_at=datetime.now() - timedelta(hours=2)
    )

    with patch('integration.utils.celery_app.control.inspect.active') as mock:
        mock.return_value = active_metadata
        reconcile_sync_connections(60)
        run_mck.assert_called_with(connection_1)


@pytest.mark.functional()
def test_update_integrations_already_exists(mock_renew_token):
    integration = create_integration('microsoft_365')
    two_days_ago = datetime.now() - timedelta(days=2)
    configuration_state = {
        'frequency': 'daily',
        'settings': {
            'groups': [
                '89243424-a0dc-42ec-9ce7-28b91d59563e',
                '1j90c6bb-aaaf-4261-9091-bfb0171933c4',
            ]
        },
    }

    with fake_microsoft_api():
        with patch('django.utils.timezone.now') as mocked_now:
            mocked_now.return_value = two_days_ago
            create_already_exists_connection_accounts(integration)

            ConnectionAccount.objects.filter(
                status=SUCCESS, configuration_state=configuration_state
            ).first().delete()
            update_integrations()
            assert (
                ConnectionAccount.objects.filter(
                    status=SUCCESS, error_code=NONE
                ).count()
                == 2
            )


EXPIRE_RESULT_ERROR = {
    "error_response": (
        "{'error': 'invalid_grant', "
        "'error_description': 'AADSTS700082: "
        "The refresh token has expired due to inactivity.', "
        "'error_codes': [700082], "
        "'timestamp': '2022-02-23 06:04:31Z', "
        "'trace_id': '8c5c0719-8da6-45e2-b871-d3add8bf0f0', "
        "'correlation_id': 'daffb6b1-2675-4e2e-a32a-5384f', "
        "'error_uri': 'https://domain/error?code=700082'}"
    )
}

LOOKUP_QUERY = {
    "result__icontains": (
        "AADSTS700082: The refresh token has expired due to inactivity."
    )
}


@pytest.mark.functional()
def test_update_connection_accounts_to_expired_token():
    integration_mock = create_integration('google_workspace')
    organization_mock = create_organization(name='organization', state=ACTIVE)
    user_mock = create_users('expired_user', organization_mock)
    expired_connection = celery_connection_account(
        integration=integration_mock,
        alias='Expired connection',
        created_by=user_mock,
        organization=organization_mock,
    )
    # Test case
    # Integration on error status that based on the result the message can
    #  tell us that the token didn't work because is expired
    expired_connection.result = EXPIRE_RESULT_ERROR
    expired_connection.status = ERROR
    expired_connection.error_code = PROVIDER_SERVER_ERROR
    expired_connection.save()

    updated_connections = update_connection_accounts_to_expired_token(**LOOKUP_QUERY)
    expired_connection.refresh_from_db()
    assert {UPDATED_CONNECTIONS: [expired_connection.id]} == updated_connections
    assert expired_connection.error_code == EXPIRED_TOKEN


@pytest.mark.functional()
def test_not_update_because_invalid_lookup_query(caplog):
    integration_mock = create_integration('google_workspace')
    organization_mock = create_organization(name='organization', state=ACTIVE)
    user_mock = create_users('expired_user', organization_mock)
    expired_connection = celery_connection_account(
        integration=integration_mock,
        alias='Expired connection 2',
        created_by=user_mock,
        organization=organization_mock,
    )
    expired_connection.result = EXPIRE_RESULT_ERROR
    expired_connection.status = ERROR
    expired_connection.error_code = PROVIDER_SERVER_ERROR
    expired_connection.save()

    # Test case Invalid Lookup query
    updated_connections = update_connection_accounts_to_expired_token(
        **{"test": "test"}
    )
    expired_connection.refresh_from_db()
    assert {UPDATED_CONNECTIONS: []} == updated_connections
    assert (
        'Error to execute query because invalid parameters: '
        '[<Q: (AND: (\'test\', \'test\'))>]. '
        'Error: Cannot resolve keyword \'test\''
        in caplog.text
    )


@pytest.mark.functional()
def test_not_update_because_not_lookup_queries(caplog):
    integration_mock = create_integration('google_workspace')
    organization_mock = create_organization(name='organization', state=ACTIVE)
    user_mock = create_users('expired_user', organization_mock)
    expired_connection = celery_connection_account(
        integration=integration_mock,
        alias='Expired connection 3',
        created_by=user_mock,
        organization=organization_mock,
    )
    expired_connection.result = EXPIRE_RESULT_ERROR
    expired_connection.status = ERROR
    expired_connection.error_code = PROVIDER_SERVER_ERROR
    expired_connection.save()

    # Test case Not lookup queries
    updated_connections = update_connection_accounts_to_expired_token()
    expired_connection.refresh_from_db()
    assert {UPDATED_CONNECTIONS: []} == updated_connections
    assert 'Not parameters for filter' in caplog.text


def celery_connection_account(
    integration: Integration,
    alias: str,
    created_by: User,
    organization: Organization,
    vendor_name: str = None,
    last_successful_run: Union[str, None] = None,
    status: str = 'success',
) -> ConnectionAccount:
    connection_account = create_connection_account(
        integration=integration,
        alias=alias,
        authentication=dict(access_token="TEST_TOKEN", refresh_token="TEST_TOKEN"),
        organization=organization,
        created_by=created_by,
        configuration_state={
            'frequency': 'daily',
            'settings': {
                'groups': [
                    '43243424-a0dc-42ec-9ce7-28b91d59563e',
                    '9f90c6bb-aaaf-4261-9091-bfb0171933c4',
                ]
            },
        },
        vendor_name=vendor_name,
        status=status,
    )
    if last_successful_run:
        connection_account.configuration_state[
            'last_successful_run'
        ] = last_successful_run
    return connection_account


def create_connection_account_with_errors(integration: Integration):
    ca_1 = 'testing 1'
    ca_2 = 'testing 2'
    ca_3 = 'testing 3'
    ca_4 = 'testing 4'
    ca_5 = 'testing 5'
    organization = create_organization(name='organization', state=ACTIVE)

    user_1 = create_users('1', organization)
    user_2 = create_users('2', organization)
    user_3 = create_users('3', organization)
    user_4 = create_users('4', organization)
    user_5 = create_users('5', organization)

    organization.compliance_architect_user = user_1
    connection_account_1 = celery_connection_account(
        integration, ca_1, user_1, organization
    )
    connection_account_2 = celery_connection_account(
        integration, ca_2, user_2, organization
    )
    connection_account_3 = celery_connection_account(
        integration, ca_3, user_3, organization
    )
    connection_account_4 = celery_connection_account(
        integration, ca_4, user_4, organization
    )
    connection_account_5 = celery_connection_account(
        integration, ca_5, user_5, organization
    )
    _set_connection_account_error(connection_account_1, PROVIDER_SERVER_ERROR, ERROR)
    _set_connection_account_error(connection_account_2, INSUFFICIENT_PERMISSIONS, ERROR)
    _set_connection_account_error(connection_account_3, DENIAL_OF_CONSENT, ERROR)
    _set_connection_account_error(connection_account_4, CONNECTION_TIMEOUT, ERROR)
    _set_connection_account_error(connection_account_5, NONE, SUCCESS)


def _set_connection_account_error(connection_account, error_type, status):
    connection_account.status = status
    connection_account.error_code = error_type
    connection_account.save()


def create_users(prefix: str, organization: Organization) -> User:
    return create_user(organization, email=f'hey-{prefix}-laika@heylaika.com')


def create_already_exists_connection_accounts(integration):
    ca_1 = 'testing 1'
    ca_2 = 'testing 2'
    ca_3 = 'testing 3'
    organization = create_organization(name='organization', state=ACTIVE)

    user_1 = create_users('1', organization)

    organization.compliance_architect_user = user_1
    create_connection_account(
        ca_1,
        authentication=dict(access_token="TEST_TOKEN", refresh_token="TEST_TOKEN"),
        organization=organization,
        integration=integration,
        created_by=user_1,
        status=SUCCESS,
        configuration_state={
            'frequency': 'daily',
            'settings': {
                'groups': [
                    '43243424-a0dc-42ec-9ce7-28b91d59563e',
                    '9f90c6bb-aaaf-4261-9091-bfb0171933c4',
                ]
            },
        },
    )
    create_connection_account(
        ca_2,
        authentication=dict(access_token="TEST_TOKEN", refresh_token="TEST_TOKEN"),
        organization=organization,
        integration=integration,
        created_by=user_1,
        status=ALREADY_EXISTS,
        configuration_state={
            'frequency': 'daily',
            'settings': {
                'groups': [
                    '89243424-a0dc-42ec-9ce7-28b91d59563e',
                    '1j90c6bb-aaaf-4261-9091-bfb0171933c4',
                ]
            },
        },
    )
    create_connection_account(
        ca_3,
        authentication=dict(access_token="TEST_TOKEN", refresh_token="TEST_TOKEN"),
        organization=organization,
        integration=integration,
        created_by=user_1,
        status=SUCCESS,
        configuration_state={
            'frequency': 'daily',
            'settings': {
                'groups': [
                    '89243424-a0dc-42ec-9ce7-28b91d59563e',
                    '1j90c6bb-aaaf-4261-9091-bfb0171933c4',
                ]
            },
        },
    )


@pytest.mark.functional()
def test_update_integrations_within_interval():
    integration = create_integration('Heroku')

    connection_alias = 'Test last run interval 2 days ago'
    organization = create_organization(name='Laika', state=ACTIVE)

    user = create_users('1', organization)

    organization.compliance_architect_user = user
    two_days_ago = (dj_tz.now() - timedelta(days=2)).timestamp()
    connection_account = celery_connection_account(
        integration=integration,
        alias=connection_alias,
        created_by=user,
        organization=organization,
        last_successful_run=two_days_ago,
    )
    _set_connection_account_error(connection_account, PROVIDER_SERVER_ERROR, ERROR)

    with patch(INTEGRATION_DELAY) as delay_mck:
        update_integrations()

        delay_mck.assert_called_once_with(
            connection_id=connection_account.id, send_mail_error=False
        )


@pytest.mark.functional()
@pytest.mark.skip()
def test_update_integrations_without_interval():
    integration = create_integration('Heroku')

    connection_alias = 'Test last run interval 40 minutes ago'
    organization = create_organization(name='Laika', state=ACTIVE)

    user = create_users('1', organization)

    organization.compliance_architect_user = user
    two_days_ago = (dj_tz.now() - timedelta(minutes=40)).timestamp()
    connection_account = celery_connection_account(
        integration=integration,
        alias=connection_alias,
        created_by=user,
        organization=organization,
        last_successful_run=two_days_ago,
    )
    _set_connection_account_error(connection_account, PROVIDER_SERVER_ERROR, ERROR)

    with patch(INTEGRATION_DELAY) as delay_mck:
        update_integrations()

        delay_mck.assert_not_called()


@pytest.mark.functional()
def test_update_integrations_not_last_run_and_out_of_interval():
    integration = create_integration('Heroku')

    connection_alias = 'Test last run interval 2 days ago'
    organization = create_organization(name='Laika', state=ACTIVE)

    user = create_users('1', organization)

    organization.compliance_architect_user = user
    connection_account = celery_connection_account(
        integration=integration,
        alias=connection_alias,
        created_by=user,
        organization=organization,
    )
    _set_connection_account_error(connection_account, PROVIDER_SERVER_ERROR, ERROR)

    with patch(INTEGRATION_DELAY) as delay_mck:
        update_integrations()

        delay_mck.assert_not_called()


@pytest.mark.functional()
def test_execute_multiple_connections():
    organization_mock = create_organization(name='test_org', state=ACTIVE)
    user_mock = create_users('test_user', organization_mock)
    sentry_account = celery_connection_account(
        integration=create_integration('sentry'),
        alias='Troubleshooting Account 1',
        created_by=user_mock,
        organization=organization_mock,
    )
    google_account = celery_connection_account(
        integration=create_integration('google'),
        alias='Troubleshooting Account 2',
        created_by=user_mock,
        organization=organization_mock,
        status='error',
    )
    gcp_account = celery_connection_account(
        integration=create_integration('gcp'),
        alias='Troubleshooting Account 3',
        created_by=user_mock,
        organization=organization_mock,
        status='pending',
    )

    executed_accounts = execute_connection_accounts(
        sentry_account.id, google_account.id, gcp_account.id
    )
    assert executed_accounts == {'executed_connections': 2}


@pytest.mark.functional()
def test_execute_multiple_without_parameters():
    executed_accounts = execute_connection_accounts()
    assert executed_accounts == {'executed_connections': 0}


def test_scale_simulator():
    with patch('integration.tasks.time.sleep') as mock:
        scale_simulator(4, 2, 5)
        assert mock.call_count == 3
