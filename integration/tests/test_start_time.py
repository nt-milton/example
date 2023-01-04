from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from integration.models import ConnectionAccount
from integration.utils import calculate_date_range, get_last_run

from .factory import create_connection_account

CURRENT_TIME = datetime(2020, 3, 5, tzinfo=timezone.utc)


@pytest.fixture
def connection_account(graphql_organization) -> ConnectionAccount:
    connection_account = create_connection_account(
        vendor_name='Vendor Test',
        alias='Connection 1',
        organization=graphql_organization,
    )
    return connection_account


@pytest.mark.functional
@freeze_time(CURRENT_TIME)
def test_configuration_state_is_empty_uses_three_semesters(
    connection_account: ConnectionAccount,
):
    date_range = calculate_date_range()
    assert connection_account.configuration_state == {}
    assert date_range == '2018-09-05'


def test_get_last_run():
    last_run = datetime(2020, 3, 1)
    connection_account = ConnectionAccount()
    new_configuration_state = {
        'last_successful_run': last_run.timestamp(),
    }
    connection_account.configuration_state = new_configuration_state

    last_run = get_last_run(connection_account)
    assert last_run == '2020-03-01'
