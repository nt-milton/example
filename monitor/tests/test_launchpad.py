import pytest

from monitor.launchpad import launchpad_mapper
from monitor.models import OrganizationMonitor
from monitor.tests.factory import create_monitor, create_organization_monitor


@pytest.mark.django_db
def test_monitor_launchpad_mapper(graphql_organization):
    monitor = create_monitor(
        'monitor name',
        'fake query..',
        validation_query=None,
        description='monitor description',
        display_id='MON-1',
    )
    organization_monitor = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor,
    )
    create_organization_monitor(monitor=monitor)

    monitors = launchpad_mapper(OrganizationMonitor, graphql_organization.id)

    assert len(monitors) == 1
    assert monitors[0].id == organization_monitor.id
    assert monitors[0].display_id == 'MON-1'
    assert monitors[0].name == 'monitor name'
    assert monitors[0].description == 'monitor description'
    assert monitors[0].url == f"/monitors/{organization_monitor.id}"
