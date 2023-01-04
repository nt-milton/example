import pytest

from integration import gitlab
from integration.account import set_connection_account_number_of_records
from integration.exceptions import ConfigurationError
from integration.gitlab import implementation
from integration.gitlab.implementation import (
    GITLAB_SYSTEM,
    N_RECORDS,
    _perform_create_access_token,
    callback,
    run,
)
from integration.gitlab.tests.fake_api import (
    fake_gitlab_api,
    fake_gitlab_self_hosted_api,
)
from integration.models import PENDING, ConnectionAccount
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import get_db_number_of_records
from integration.views import oauth_callback

INTEGRATION_USER = 'Integration User'

FAKE_CLIENT_ID = 'fake_client_id'
FAKE_CLIENT_SECRET = 'fake_client_secret'
FAKE_ACCESS_TOKEN = 'fake_access_token'
FAKE_REFRESH_TOKEN = 'fake_resfresh_token'


@pytest.fixture
def connection_account():
    # Omit validation for testing purpose
    # because sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    with fake_gitlab_api():
        yield gitlab_connection_account()


@pytest.fixture
def connection_account_without_groups():
    # Omit validation for testing purpose
    # because sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    with fake_gitlab_api():
        yield gitlab_connection_account_without_groups()


@pytest.fixture
def self_hosted_connection_account():
    # Omit validation for testing purpose
    # because sqlite does not support contains
    def omit_duplicate(connection_account):
        pass

    implementation.raise_if_duplicate = omit_duplicate
    with fake_gitlab_self_hosted_api():
        yield gitlab_self_hosted_connection_account()


@pytest.mark.functional
def test_gitlab_denial_of_consent_validation(connection_account):
    with pytest.raises(ConfigurationError):
        callback(None, 'redirect_uri', connection_account)


@pytest.mark.functional
def test_gitlab_callback_status(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, GITLAB_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    prefetch_options = connection_account.authentication['prefetch_group']
    assert prefetch_options == _expected_group_custom_options()
    assert connection_account.status == PENDING


@pytest.mark.functional
def test_gitlab_integrate_account_number_of_records(connection_account):
    run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


@pytest.mark.functional
def test_raise_error_for_unknown_field(connection_account):
    with pytest.raises(NotImplementedError):
        gitlab.get_custom_field_options("organization", connection_account)


@pytest.mark.functional
def test_gitlab_integration_get_custom_field_options(connection_account):
    expected_groups = _expected_group_custom_options()
    groups = gitlab.get_custom_field_options('group', connection_account)

    assert groups.options == expected_groups


@pytest.mark.functional
def test_access_token_refreshed(connection_account):
    prev_access_token = connection_account.authentication['access_token']
    access_token = _perform_create_access_token(connection_account)
    assert access_token != prev_access_token


def gitlab_connection_account(**kwargs):
    return create_connection_account(
        'Gitlab',
        authentication=dict(
            access_token=FAKE_ACCESS_TOKEN, refresh_token=FAKE_REFRESH_TOKEN
        ),
        configuration_state=dict(
            settings={
                'visibility': ["PUBLIC", "PRIVATE"],
                'groups': ['laika-test-one', 'laika-test-two'],
            },
        ),
        **kwargs
    )


def gitlab_self_hosted_connection_account(**kwargs):
    return create_connection_account(
        'Gitlab',
        authentication=dict(
            access_token=FAKE_ACCESS_TOKEN, refresh_token=FAKE_REFRESH_TOKEN
        ),
        configuration_state=dict(
            credentials={
                'baseUrl': 'https://gitlab.development.heylaika.com',
                'clientId': 'test-client_id',
                'secretId': 'test_secret_id',
            },
            settings={
                'visibility': ["PUBLIC", "PRIVATE"],
                'groups': ['laika-test-one', 'laika-test-two'],
            },
            subscriptionType='SELF',
        ),
        **kwargs
    )


def gitlab_connection_account_without_groups(**kwargs):
    return create_connection_account(
        'Gitlab',
        authentication=dict(
            access_token=FAKE_ACCESS_TOKEN, refresh_token=FAKE_REFRESH_TOKEN
        ),
        configuration_state=dict(
            settings={
                'visibility': ["PUBLIC", "PRIVATE"],
            },
        ),
        **kwargs
    )


def _expected_group_custom_options():
    return [
        {'id': 'laika-test-one', 'value': {'name': 'laika-test-1'}},
        {'id': 'laika-test-two', 'value': {'name': 'laika-test-2'}},
        {'id': 'laika-test-three', 'value': {'name': 'laika-test-3'}},
        {'id': 'laika-test-four', 'value': {'name': 'laika-test-4'}},
    ]
