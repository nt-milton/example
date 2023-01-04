from unittest import mock
from unittest.mock import patch
from uuid import uuid4

import pytest
from log_request_id import local

from integration.models import PAYROLL, ConnectionAccount, Integration
from integration.tests import create_connection_account
from integration.tests.factory import create_integration


@pytest.fixture
def my_finch_integration() -> Integration:
    return create_integration(
        vendor_name='BambooHR',
        metadata={
            'finchProvider': 'bamboo_hr',
        },
        category=PAYROLL,
    )


@pytest.fixture
def payroll_connection_account(
    graphql_organization, graphql_user, my_finch_integration
) -> ConnectionAccount:
    connection_account = create_connection_account(
        'BambooHR',
        integration=my_finch_integration,
        created_by=graphql_user,
        organization=graphql_organization,
    )
    connection_account.save = mock.Mock(return_value=None)
    return connection_account


@pytest.mark.django_db
@patch('integration.models.eda_publisher')
def test_broadcast_payroll_connection_account_success(
    mock_eda_publisher, payroll_connection_account
):
    mock_eda_publisher.submit_event.return_value = True
    local.request_id = str(uuid4())

    with payroll_connection_account.connection_attempt():
        pass
    mock_eda_publisher.submit_event.assert_called_once()
