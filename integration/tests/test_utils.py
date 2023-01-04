from unittest.mock import patch

import pytest

from integration.encryption_utils import (
    decrypt_value,
    encrypt_value,
    get_decrypted_or_encrypted_auth_value,
)
from integration.models import ConnectionAccount, ErrorCatalogue
from integration.tests import create_connection_account
from integration.utils import (
    _get_wizard_error_message,
    get_celery_workers_metrics,
    integration_workers,
    push_worker_metric,
)


@pytest.mark.functional
def test_default_wizard_message(graphql_organization):
    connection_account = create_connection_account(
        'testing',
        alias='testing_connection',
        organization=graphql_organization,
        authentication={},
    )
    connection_account.error_code = '006'
    connection_account.save()
    object_error = {
        'code': '006',
        'failure_reason_mail': 'error',
        'send_email': False,
        'description': 'failed',
        'default_message': '<p>default message</p>',
        'default_wizard_message': '<p>default wizard message</p>',
    }
    error_in_catalogue = ErrorCatalogue.objects.create(**object_error)
    error_message = _get_wizard_error_message(connection_account, error_in_catalogue)
    assert error_message == '<p>default wizard message</p>'


@pytest.fixture
def queue_metadata():
    queue_metadata = {
        'celery@2eede3e1413b': [
            {
                'name': 'long_run',
                'routing_key': 'long_run',
            }
        ],
        'celery@b8ebdae306b8': [
            {
                'name': 'celery',
                'routing_key': 'celery',
            }
        ],
    }
    with patch('integration.utils.celery_app.control.inspect.active_queues') as mock:
        mock.return_value = queue_metadata
        yield


@pytest.fixture
def active_metadata():
    active_metadata = {
        'celery@b8ebdae306b8': [
            {'id': 'task-000', 'type': 'another_app.tasks.dummy_task'}
        ],
        'celery@2eede3e1413b': [
            {'id': 'task-123', 'type': 'integration.tasks.dummy_task'}
        ],
    }
    with patch('integration.utils.celery_app.control.inspect.active') as mock:
        mock.return_value = active_metadata


def test_filter_integration_workers(queue_metadata):
    workers = integration_workers()
    assert workers == ['celery@2eede3e1413b']


def test_worker_metrics(queue_metadata):
    active_metadata = {
        'celery@b8ebdae306b8': [
            {'id': 'task-000', 'type': 'another_app.tasks.dummy_task'}
        ],
        'celery@2eede3e1413b': [
            {'id': 'task-123', 'type': 'integration.tasks.dummy_task'}
        ],
    }
    with patch('integration.utils.celery_app.control.inspect.active') as mock:
        mock.return_value = active_metadata
        metrics = get_celery_workers_metrics()
        assert metrics == dict(total=1, busy=1, idle=0)


def test_push_worker_metric(queue_metadata, active_metadata):
    with patch('integration.utils.is_worker') as mock_worker, patch(
        'integration.utils.boto3'
    ) as mock_boto:
        mock_worker.return_value = True
        push_worker_metric()
        assert mock_boto.client.call_count == 1


@pytest.mark.functional
def test_decrypted_or_encrypted_auth_no_flag(connection_account_with_auth):
    get_decrypted_or_encrypted_auth_value(connection_account_with_auth)
    access_token = ConnectionAccount.objects.get(
        id=connection_account_with_auth.id
    ).authentication['access_token']

    assert access_token == "TEST_TOKEN"


@pytest.mark.functional
def test_decrypted_or_encrypted_auth_with_flag(connection_account_with_auth):
    connection_account_with_auth.integration.metadata['add_encryption'] = True
    get_decrypted_or_encrypted_auth_value(connection_account_with_auth)
    access_token = ConnectionAccount.objects.get(
        id=connection_account_with_auth.id
    ).authentication['access_token']

    assert decrypt_value(access_token) == "TEST_TOKEN"


@pytest.mark.functional
def test_already_decrypted_auth_with_flag(connection_account_with_auth):
    connection_account_with_auth.integration.metadata['add_encryption'] = True
    connection_account_with_auth.authentication['access_token'] = encrypt_value(
        "TEST_TOKEN"
    )
    connection_account_with_auth.save()
    get_decrypted_or_encrypted_auth_value(connection_account_with_auth)
    access_token = ConnectionAccount.objects.get(
        id=connection_account_with_auth.id
    ).authentication['access_token']

    assert decrypt_value(access_token) == "TEST_TOKEN"


@pytest.fixture
def connection_account_with_auth(graphql_organization):
    return create_connection_account(
        'testing',
        alias='testing_connection',
        organization=graphql_organization,
        authentication=dict(access_token="TEST_TOKEN", refresh_token="TEST_TOKEN"),
    )
