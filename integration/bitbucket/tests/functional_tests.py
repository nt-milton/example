import pytest

from integration import bitbucket
from integration.account import set_connection_account_number_of_records
from integration.bitbucket.implementation import (
    BITBUCKET_SYSTEM,
    N_RECORDS,
    callback,
    run,
)
from integration.bitbucket.tests.fake_api import fake_bitbucket_api
from integration.exceptions import ConfigurationError
from integration.models import PENDING, ConnectionAccount
from integration.tests import create_connection_account, create_request_for_callback
from integration.tests.factory import get_db_number_of_records
from integration.views import oauth_callback

FAKE_CLIENT_ID = 'fake_client_id'
FAKE_CLIENT_SECRET = 'fake_client_secret'
FAKE_REFRESH_TOKEN = 'fake_resfresh_token'


@pytest.fixture
def connection_account():
    with fake_bitbucket_api():
        yield bitbucket_connection_account()


@pytest.mark.functional
def test_bitbucket_denial_of_consent_validation(connection_account):
    with pytest.raises(ConfigurationError):
        callback(None, 'redirect_uri', connection_account)


@pytest.mark.functional
def test_bitbucket_callback_status(connection_account):
    request = create_request_for_callback(connection_account)
    oauth_callback(request, BITBUCKET_SYSTEM)
    connection_account = ConnectionAccount.objects.get(
        control=connection_account.control
    )
    assert connection_account.status == PENDING


@pytest.mark.functional
def test_bitbucket_integrate_account_number_of_records(connection_account):
    run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


def bitbucket_connection_account(**kwargs):
    return create_connection_account(
        'BitBucket',
        authentication=dict(
            client_id=FAKE_CLIENT_ID,
            client_secret=FAKE_CLIENT_SECRET,
            refresh_token=FAKE_REFRESH_TOKEN,
        ),
        configuration_state=dict(
            settings={
                "visibility": ["PUBLIC", "PRIVATE"],
                "workspaces": [
                    {
                        "id": "dev_heylaika",
                        "value": {"name": "Dev Team"},
                        "__typename": "OptionType",
                    },
                    {
                        "id": "bitbucket-settings",
                        "value": {"name": "Bitbucket Settings"},
                        "__typename": "OptionType",
                    },
                ],
            }
        ),
        **kwargs
    )


@pytest.mark.functional
def test_get_custom_field_options(connection_account):
    get_workspaces_options = bitbucket.get_custom_field_options(
        "workspace", connection_account
    )
    expected_workspaces = [
        {'id': 'albertwilliams_xyz', 'value': {'name': 'Albert J. Williams'}},
        {'id': 'albert_at_hey_laika', 'value': {'name': 'Albert Williams'}},
    ]
    first_element = get_workspaces_options.options[0]
    first_id = first_element['id']
    first_name = first_element['value']['name']
    assert first_id == expected_workspaces[0]['id']
    assert first_name == expected_workspaces[0]['value']['name']

    second_element = get_workspaces_options.options[1]
    first_id = second_element['id']
    first_name = second_element['value']['name']
    assert first_id == expected_workspaces[1]['id']
    assert first_name == expected_workspaces[1]['value']['name']


@pytest.mark.functional
def test_raise_error_for_unknown_field(connection_account):
    with pytest.raises(NotImplementedError):
        bitbucket.get_custom_field_options("project", connection_account)


@pytest.mark.functional
def test_get_selected_workspaces(connection_account):
    connection_account.settings['workspaces'] = 'All Workspaces Selected'
    bitbucket.run(connection_account)
    assert len(connection_account.settings['workspaces']) > 1
