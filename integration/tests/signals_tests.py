from unittest.mock import patch

import pytest

from laika.celery import MAX_PRIORITY
from monitor.events import integration_events

from ..constants import SETUP_COMPLETE
from .factory import create_connection_account, create_integration


@pytest.mark.functional
@pytest.mark.parametrize(
    'vendor_name, expected_integration',
    [
        ('AWS', 'aws_dependency'),
        ('Google Cloud Platform', 'gcp_dependency'),
        ('Microsoft Azure', 'azure_dependency'),
    ],
)
def test_events_by_integration(vendor_name, expected_integration):
    integration = create_integration(
        vendor_name, metadata={'laika_objects': 'user,account,repository'}
    )
    ca_integretion = create_connection_account('ca_1', integration=integration)
    expected = {
        expected_integration,
        'lo_users_dependency',
        'lo_accounts_dependency',
        'lo_repositories_dependency',
    }
    assert (
        integration_events(
            ca_integretion.integration.vendor.name,
            ca_integretion.integration.laika_objects(),
        )
        == expected
    )


@pytest.mark.functional
def test_celery_schedule_max_priority():
    with patch('integration.signals.run_initial_and_notify_monitors') as mock:
        ca = create_connection_account('ca_1')
        ca.integration.metadata = {'celery_execution': True}
        ca.integration.save()
        ca.status = SETUP_COMPLETE
        ca.save()
        mock.apply_async.assert_called_with(
            args=[ca.id], countdown=1, priority=MAX_PRIORITY
        )
