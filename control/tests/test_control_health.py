from datetime import datetime, timedelta

import pytest

from control.tests.factory import create_action_item, create_control
from feature.constants import new_controls_feature_flag
from feature.models import Flag
from monitor.models import MonitorInstanceStatus, MonitorStatus
from monitor.tests.factory import create_monitor, create_organization_monitor


@pytest.fixture()
def organization_monitor_healthy(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(name='Monitor Test', query='select name from test'),
    )


@pytest.fixture()
def organization_monitor_inactive_triggered(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(
            name='Test Monitor 2',
            query='SELECT id FROM monitors WHERE id=1',
            status=MonitorStatus.INACTIVE,
        ),
        active=False,
        status=MonitorInstanceStatus.TRIGGERED,
    )


@pytest.fixture()
def organization_monitor_active_triggered(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(
            name='Test Monitor 4',
            query='select status from test',
            status=MonitorStatus.INACTIVE,
        ),
        active=True,
        status=MonitorInstanceStatus.TRIGGERED,
    )


@pytest.fixture()
def control(graphql_organization):
    return create_control(
        organization=graphql_organization, display_id=1, name='Control Test'
    )


@pytest.fixture()
def action_items():
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    action_item_new_unexpired = create_action_item(
        name="Action Item new unexpired", status="new", due_date=tomorrow
    )
    action_item_new_expired = create_action_item(
        name="Action Item new expired", status="new", due_date=today
    )
    action_item_completed_expired = create_action_item(
        name="Action Item completed unexpired", status="new", due_date=tomorrow
    )
    action_item_not_aplicable_expired = create_action_item(
        name="Action Item not applicable unexpired",
        status="not_applicable",
        due_date=tomorrow,
    )
    return (
        action_item_new_unexpired,
        action_item_new_expired,
        action_item_completed_expired,
        action_item_not_aplicable_expired,
    )


@pytest.fixture()
def flag(graphql_organization):
    Flag.objects.get_or_create(
        name=new_controls_feature_flag,
        organization=graphql_organization,
        defaults={'is_enabled': True},
    )


@pytest.mark.django_db
def test_control_health_needs_attention_by_LAI(
    graphql_organization, control, action_items, organization_monitor_healthy, flag
):
    """
    Test the control health with healthy monitor and
    action item new and expired
    """
    _, action_item_new_expired, *_ = action_items
    control.organization_monitors.add(organization_monitor_healthy)
    control.action_items.add(action_item_new_expired)
    control.status = "IMPLEMENTED"
    control.save()
    assert control.health == "FLAGGED"


@pytest.mark.django_db
def test_control_health_operational(
    graphql_organization, control, action_items, organization_monitor_healthy, flag
):
    """
    Test the control health with healthy monitor and
    action item new and unexpired
    """
    action_item_new_unexpired, *_ = action_items
    control.organization_monitors.add(organization_monitor_healthy)
    control.action_items.add(action_item_new_unexpired)
    control.status = "IMPLEMENTED"
    control.save()
    assert control.health == "HEALTHY"


@pytest.mark.django_db
def test_control_health_needs_attention_by_monitor(
    graphql_organization,
    control,
    action_items,
    organization_monitor_active_triggered,
    flag,
):
    """
    Test the control health with triggered monitor and
    action item new and unexpired
    """
    action_item_new_unexpired, *_ = action_items
    control.organization_monitors.add(organization_monitor_active_triggered)
    control.action_items.add(action_item_new_unexpired)
    control.status = "IMPLEMENTED"
    control.save()
    assert control.health == "FLAGGED"


@pytest.mark.django_db
def test_control_health_operational_expired_not_new(
    graphql_organization, control, action_items, organization_monitor_healthy, flag
):
    """
    Test the control health with healthy monitor and
    action items new unexpired and expired but not new
    """
    (
        action_item_new_unexpired,
        _,
        action_item_completed_expired,
        action_item_not_aplicable_expired,
    ) = action_items

    control.organization_monitors.add(organization_monitor_healthy)
    control.action_items.add(
        action_item_new_unexpired,
        action_item_completed_expired,
        action_item_not_aplicable_expired,
    )
    control.status = "IMPLEMENTED"
    control.save()
    assert control.health == "HEALTHY"


@pytest.mark.django_db
def test_control_health_operational_without_monitors(
    graphql_organization, control, action_items, flag
):
    """
    Test the control health without monitors and
    action item new and unexpired
    """
    (
        action_item_new_unexpired,
        _,
        action_item_completed_expired,
        action_item_not_aplicable_expired,
    ) = action_items

    control.action_items.add(
        action_item_new_unexpired,
        action_item_completed_expired,
        action_item_not_aplicable_expired,
    )
    control.status = "IMPLEMENTED"
    control.save()
    assert control.health == "HEALTHY"


@pytest.mark.django_db
def test_control_health_operational_not_action_item(
    graphql_organization, control, action_items, organization_monitor_healthy, flag
):
    """
    Test the control health with healthy monitor and
    no action items
    """
    control.organization_monitors.add(organization_monitor_healthy)
    control.status = "IMPLEMENTED"
    control.save()
    assert control.health == "HEALTHY"


@pytest.mark.django_db
def test_control_health_needs_attention_not_action_item(
    graphql_organization,
    control,
    action_items,
    organization_monitor_active_triggered,
    flag,
):
    """
    Test the control health with triggerd monitor and
    no action items
    """
    control.organization_monitors.add(organization_monitor_active_triggered)
    control.status = "IMPLEMENTED"
    control.save()
    assert control.health == "FLAGGED"


@pytest.mark.django_db
def test_control_health_operational_with_inactive_monitor(
    graphql_organization,
    control,
    action_items,
    organization_monitor_inactive_triggered,
    flag,
):
    """
    Test the control health with healthy monitor and
    action item new and unexpired
    """
    action_item_new_unexpired, *_ = action_items
    control.organization_monitors.add(organization_monitor_inactive_triggered)
    control.action_items.add(action_item_new_unexpired)
    control.status = "IMPLEMENTED"
    control.save()
    assert control.health == "HEALTHY"
