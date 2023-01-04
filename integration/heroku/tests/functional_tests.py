import json
from typing import Dict

import pytest

from integration import heroku
from integration.account import set_connection_account_number_of_records
from integration.encryption_utils import decrypt_value
from integration.exceptions import ConnectionAlreadyExists
from integration.heroku import implementation
from integration.heroku.implementation import N_RECORDS
from integration.heroku.mapper import HEROKU_SYSTEM
from integration.heroku.tests.fake_api import fake_heroku_api, teams_response
from integration.models import ConnectionAccount
from integration.tests import create_connection_account
from integration.tests.factory import get_db_number_of_records
from user.tests import create_user


@pytest.fixture
def connection_account():
    with fake_heroku_api():
        yield heroku_connection_account()


@pytest.fixture
def connection_account_for_connect():
    with fake_heroku_api():
        yield heroku_connection_account_for_connect()


@pytest.mark.functional
def test_heroku_connect(connection_account_for_connect):
    heroku.implementation.connect(connection_account_for_connect)
    ca = ConnectionAccount.objects.get(id=connection_account_for_connect.id)
    expected_teams = json.loads(teams_response())
    assert expected_teams == ca.authentication.get('allTeams')


@pytest.mark.functional
def test_heroku_connect_decrypt_api_key(connection_account_for_connect):
    api_key = connection_account_for_connect.credentials['apiKey']
    heroku.implementation.connect(connection_account_for_connect)
    encrypted_api_key = connection_account_for_connect.credentials['apiKey']
    assert api_key == decrypt_value(encrypted_api_key)


@pytest.mark.functional
def test_heroku_integrate_account_number_of_records(connection_account):
    heroku.run(connection_account)
    result = get_db_number_of_records(connection_account)
    expected = str(
        set_connection_account_number_of_records(connection_account, N_RECORDS)
    )
    assert result == expected


def heroku_connection_account(**kwargs):
    return create_connection_account(
        HEROKU_SYSTEM,
        authentication={
            "allTeams": [
                {'id': '01234567-89ab-cdef-0123-456789abcdef', 'name': 'example'}
            ]
        },
        configuration_state=_configuration_state(),
        **kwargs
    )


@pytest.mark.functional
def test_raise_if_is_duplicate(connection_account):
    created_by = create_user(
        connection_account.organization, email='heylaika+test+vetty+ca@heylaika.com'
    )
    create_connection_account(
        'heroku-duplicate',
        authentication={},
        organization=connection_account.organization,
        integration=connection_account.integration,
        created_by=created_by,
        configuration_state=_configuration_state(),
    )
    with pytest.raises(ConnectionAlreadyExists):
        implementation.run(connection_account)


def heroku_connection_account_for_connect(**kwargs):
    return create_connection_account(
        HEROKU_SYSTEM, configuration_state=_configuration_state(), **kwargs
    )


def _configuration_state() -> Dict:
    return {
        "settings": {
            "selectedTeams": [
                "01234567-89ab-cdef-0123-456789abcdef",
            ]
        },
        "credentials": {
            "email": "dev@heylaika.com",
            "apiKey": "fcaa48be-2c94-4877-83eb-d90168f4f320",
        },
        "last_successful_run": 1641845767.858797,
    }
