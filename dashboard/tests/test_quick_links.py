import pytest
from django.utils.timezone import now

from control.tests import create_control
from control.tests.factory import create_action_item
from dashboard.quicklinks.quick_link_classes import (
    ControlQuickLink,
    IntegrationQuickLink,
    MonitorQuickLink,
    PolicyQuickLink,
)
from dashboard.tests.queries import GET_QUICK_LINKS
from feature.constants import new_controls_feature_flag
from feature.models import Flag
from integration.constants import ERROR, SUCCESS
from integration.tests.factory import create_connection_account
from monitor.models import MonitorInstanceStatus
from monitor.tests.factory import create_monitor, create_organization_monitor
from policy.tests.factory import create_empty_policy
from user.tests import create_user


@pytest.fixture(name='_flag')
def fixture_flag(graphql_organization):
    Flag.objects.get_or_create(
        name=new_controls_feature_flag,
        organization=graphql_organization,
        defaults={'is_enabled': True},
    )


@pytest.fixture(name='_controls')
def fixture_control(graphql_organization):
    control1 = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test 1',
        description='Control description',
        implementation_notes='',
        status='IMPLEMENTED',
    )

    control2 = create_control(
        organization=graphql_organization,
        display_id=2,
        name='Control Test 2',
        description='Control description',
        implementation_notes='',
        status='IMPLEMENTED',
    )

    control3 = create_control(
        organization=graphql_organization,
        display_id=3,
        name='Control Test 3',
        description='Control description',
        implementation_notes='',
        status='IMPLEMENTED',
    )
    return control1, control2, control3


@pytest.fixture(name='_triggered_organization_monitors')
def fixture_triggered_organization_monitors(graphql_organization):
    monitor1 = create_monitor(name='monitor1', query='select * from people;')
    monitor2 = create_monitor(name='monitor2', query='select * from people;')
    organization_monitor1 = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor1,
        status=MonitorInstanceStatus.TRIGGERED,
    )
    organization_monitor2 = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor2,
        status=MonitorInstanceStatus.TRIGGERED,
    )

    return organization_monitor1, organization_monitor2


@pytest.fixture(name='_healthy_organization_monitors')
def fixture_healthy_organization_monitors(graphql_organization):
    monitor1 = create_monitor(name='monitor1', query='select * from people;')
    monitor2 = create_monitor(name='monitor2', query='select * from people;')
    organization_monitor3 = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor1,
        status=MonitorInstanceStatus.HEALTHY,
    )
    organization_monitor4 = create_organization_monitor(
        organization=graphql_organization,
        monitor=monitor2,
        status=MonitorInstanceStatus.HEALTHY,
    )

    return organization_monitor3, organization_monitor4


@pytest.fixture(name='_action_item')
def fixture_action_item():
    return create_action_item(
        name='LAI-001',
        description='Action item description',
        status='new',
        due_date=now(),
    )


@pytest.fixture(name='_control_setup')
def fixture_control_setup(_controls, _action_item):
    control1, control2, *_ = _controls
    control1.action_items.add(_action_item)
    control2.action_items.add(_action_item)


@pytest.fixture(name='_published_policy')
def fixture_published_policy(graphql_organization, graphql_user):
    policy = create_empty_policy(organization=graphql_organization, user=graphql_user)
    policy.is_published = True
    policy.save()
    return policy


@pytest.fixture(name='_unpublished_policy')
def fixture_unpublished_policy(graphql_organization, graphql_user):
    return create_empty_policy(organization=graphql_organization, user=graphql_user)


@pytest.fixture(name='_integration_created_connection')
def fixture_integration_created_connection(graphql_organization):
    integration_created_connection0 = create_connection_account(
        'testing',
        organization=graphql_organization,
        status=SUCCESS,
        created_by=create_user(graphql_organization, email='heylaika1@heylaika.com'),
    )

    integration_created_connection1 = create_connection_account(
        'testing2',
        organization=graphql_organization,
        status=ERROR,
        created_by=create_user(graphql_organization, email='heylaika2@heylaika.com'),
    )

    return (integration_created_connection0, integration_created_connection1)


@pytest.mark.django_db
def test_get_control_quick_link(
    graphql_organization, _controls, _action_item, _flag, _control_setup
):
    """
    This is a unit test for Class ControlQuickLink
    """
    control_quick_link = ControlQuickLink()
    quick_link_data = control_quick_link.get_quick_link(graphql_organization)

    assert quick_link_data.id == 'control'
    assert quick_link_data.name == 'Controls'
    assert quick_link_data.total == 3
    assert quick_link_data.data_number == 2


@pytest.mark.django_db
def test_get_monitor_quick_link(
    graphql_organization,
    _triggered_organization_monitors,
    _healthy_organization_monitors,
):
    """
    This is a unit test for Class MonitorQuickLink
    """
    monitor_quick_link = MonitorQuickLink()
    quick_link_data = monitor_quick_link.get_quick_link(graphql_organization)

    assert quick_link_data.id == 'monitor'
    assert quick_link_data.name == 'Monitors'
    assert quick_link_data.total == 4
    assert quick_link_data.data_number == 2


@pytest.mark.django_db
def test_get_policy_quick_link(
    graphql_organization, _published_policy, _unpublished_policy
):
    policy_quick_link = PolicyQuickLink()
    quick_link_data = policy_quick_link.get_quick_link(graphql_organization)

    assert quick_link_data.id == 'policy'
    assert quick_link_data.name == 'Policies & Procedures'
    assert quick_link_data.total == 2
    assert quick_link_data.data_number == 1


@pytest.mark.django_db
def test_get_integration_quick_link(
    graphql_organization, _integration_created_connection
):
    integration_quick_link = IntegrationQuickLink()
    quick_link_data = integration_quick_link.get_quick_link(graphql_organization)

    assert quick_link_data.id == 'integration'
    assert quick_link_data.name == 'Integrations'
    assert quick_link_data.total == 2
    assert quick_link_data.data_number == 1


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_get_quick_links(
    graphql_client,
    graphql_organization,
    _controls,
    _action_item,
    _flag,
    _control_setup,
    _published_policy,
    _unpublished_policy,
    _triggered_organization_monitors,
    _healthy_organization_monitors,
    _integration_created_connection,
):
    """
    This is a functional test for query quick_links
    """
    response = graphql_client.execute(GET_QUICK_LINKS)

    response_list = response['data']['quickLinks']
    control_data = response_list[0]
    policy_data = response_list[1]
    monitor_data = response_list[2]
    integration_data = response_list[3]

    assert control_data['id'] == 'control'
    assert control_data['name'] == 'Controls'
    assert control_data['total'] == 3
    assert control_data['dataNumber'] == 2

    assert policy_data['id'] == 'policy'
    assert policy_data['name'] == 'Policies & Procedures'
    assert policy_data['total'] == 2
    assert policy_data['dataNumber'] == 1

    assert monitor_data['id'] == 'monitor'
    assert monitor_data['name'] == 'Monitors'
    assert monitor_data['total'] == 4
    assert monitor_data['dataNumber'] == 2

    assert integration_data['id'] == 'integration'
    assert integration_data['name'] == 'Integrations'
    assert integration_data['total'] == 2
    assert integration_data['dataNumber'] == 1
