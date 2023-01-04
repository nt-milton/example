from unittest.mock import patch

import pytest

from dashboard.models import (
    DefaultTask,
    Task,
    TaskSubTypes,
    TaskTypes,
    UserTask,
    UserTaskStatus,
)
from monitor.action_item import (
    create_monitor_user_task,
    create_or_update_monitor_task,
    reconcile_action_items,
    update_or_create_user_task,
)
from monitor.models import MonitorInstanceStatus, MonitorUrgency
from monitor.tests.factory import create_monitor, create_organization_monitor
from user.constants import ROLE_SUPER_ADMIN
from user.tests import create_user

NOT_STARTED = 'not_started'
COMPLETED = 'completed'
HEALTHY = MonitorInstanceStatus.HEALTHY
TRIGGERED = MonitorInstanceStatus.TRIGGERED
NO_DATA_DETECTED = MonitorInstanceStatus.NO_DATA_DETECTED
URGENCY_URGENT = MonitorUrgency.URGENT
URGENCY_STANDARD = MonitorUrgency.STANDARD
URGENCY_LOW = MonitorUrgency.LOW
task_name = DefaultTask.MONITOR_TASK


@pytest.fixture
def admin_user(graphql_organization):
    return create_user(
        graphql_organization,
        email='admin@heylaika.com',
        role=ROLE_SUPER_ADMIN,
        first_name='admin',
    )


@pytest.fixture()
def organization_monitor(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(name='Monitor Test', query='select name from test'),
    )


@pytest.fixture()
def second_organization_monitor(graphql_organization):
    return create_organization_monitor(
        organization=graphql_organization,
        monitor=create_monitor(name='Monitor Test 2', query='select name from test'),
    )


@pytest.fixture()
def watchers(admin_user):
    return [admin_user]


@pytest.fixture
def triggered_urgent_organization_monitor(organization_monitor):
    organization_monitor.status = TRIGGERED
    organization_monitor.monitor.urgency = URGENCY_URGENT
    return organization_monitor


def create_monitor_task(id):
    return Task.objects.create(
        name=f'{task_name} {id}',
        description='Monitor task',
        task_type=TaskTypes.MONITOR_TASK,
        task_subtype=TaskSubTypes.MONITOR,
    )


def create_user_task(task, user, organization_monitor):
    return UserTask.objects.create(
        task=task,
        organization=user.organization,
        assignee=user,
        status=UserTaskStatus.NOT_STARTED,
        organization_monitor=organization_monitor,
    )


def find_pending_action_items(organization_monitor):
    return UserTask.objects.filter(
        organization_monitor=organization_monitor,
        status=UserTaskStatus.NOT_STARTED,
        task__name=f'{task_name} {organization_monitor.id}',
    )


@pytest.mark.functional
def test_reconcile_monitor_no_data_source(organization_monitor, admin_user):
    organization_monitor.status = NO_DATA_DETECTED
    reconcile_action_items(organization_monitor)
    assert not Task.objects.exists()
    assert not UserTask.objects.exists()


@pytest.mark.functional
def test_reconcile_monitor_delete_action_items_for_no_active(
    organization_monitor, admin_user
):
    task = create_or_update_monitor_task(organization_monitor.id)
    update_or_create_user_task(organization_monitor, task, admin_user)
    organization_monitor.monitor.urgency = URGENCY_STANDARD
    organization_monitor.active = False
    reconcile_action_items(organization_monitor)
    assert not UserTask.objects.exists()


@pytest.mark.functional
def test_reconcile_remove_action_items_for_urgency_low(
    organization_monitor, admin_user
):
    organization_monitor.monitor.urgency = URGENCY_LOW
    task = create_or_update_monitor_task(organization_monitor.id)
    update_or_create_user_task(organization_monitor, task, admin_user)
    reconcile_action_items(organization_monitor)
    assert not UserTask.objects.exists()


@pytest.mark.functional
def test_reconcile_healthy_complete_actions_items(organization_monitor, admin_user):
    organization_monitor.status = HEALTHY
    organization_monitor.monitor.urgency = URGENCY_URGENT
    task = create_or_update_monitor_task(organization_monitor.id)
    update_or_create_user_task(organization_monitor, task, admin_user)
    reconcile_action_items(organization_monitor)
    assert UserTask.objects.filter(
        organization_monitor=organization_monitor, status=UserTaskStatus.COMPLETED
    ).exists()


@pytest.mark.functional
def test_reconcile_update_completed_action_item_with_new_triggered(
    triggered_urgent_organization_monitor, watchers
):
    create_completed_action_items(triggered_urgent_organization_monitor, watchers)
    reconcile_action_items(triggered_urgent_organization_monitor)
    assert UserTask.objects.filter(
        organization_monitor=triggered_urgent_organization_monitor,
        status=UserTaskStatus.NOT_STARTED,
    ).exists()


urgency_parameters = [
    (URGENCY_URGENT, True, True),
    (URGENCY_STANDARD, False, True),
    (URGENCY_LOW, False, False),
]


@pytest.mark.functional
@pytest.mark.parametrize('urgency,email_sent,created', urgency_parameters)
def test_actions_item_is_created(
    urgency, email_sent, created, organization_monitor, watchers
):
    assign_organization_monitor_watchers(organization_monitor, watchers)
    organization_monitor.status = TRIGGERED
    organization_monitor.monitor.urgency = urgency
    with patch('monitor.action_item.send_email') as mock:
        reconcile_action_items(organization_monitor)
        assert mock.called == email_sent
    assert (
        UserTask.objects.filter(
            organization_monitor=organization_monitor, status=UserTaskStatus.NOT_STARTED
        ).exists()
        == created
    )


def assign_organization_monitor_watchers(organization_monitor, watchers):
    organization_monitor.watcher_list.users.add(watchers[0])


def create_completed_action_items(organization_monitor, watchers):
    assign_organization_monitor_watchers(organization_monitor, watchers)
    create_monitor_user_task(organization_monitor, watchers)
    user_task = UserTask.objects.filter(
        organization_monitor=organization_monitor
    ).first()
    user_task.status = UserTaskStatus.COMPLETED
    user_task.save()


@pytest.mark.functional
def test_create_monitor_task(organization_monitor, watchers):
    create_monitor_user_task(organization_monitor, watchers)
    assert Task.objects.filter(name=f'{task_name} {organization_monitor.id}').exists()


@pytest.mark.functional
def test_create_monitor_task_is_not_duplicated(organization_monitor, watchers):
    create_monitor_task(organization_monitor.id)
    create_monitor_user_task(organization_monitor, watchers)
    assert Task.objects.exists()


@pytest.mark.functional
def test_create_monitor_user_task(organization_monitor, watchers):
    create_monitor_user_task(organization_monitor, watchers)
    assert find_pending_action_items(organization_monitor).exists()


@pytest.mark.functional
def test_create_monitor_user_task_not_duplicated_user_task(
    organization_monitor, watchers
):
    task = create_monitor_task(organization_monitor.id)
    create_user_task(task, watchers[0], organization_monitor)
    create_monitor_user_task(organization_monitor, watchers)
    assert find_pending_action_items(organization_monitor).count() == 1


@pytest.mark.functional
def test_create_action_item_with_new_watcher_list_user(
    triggered_urgent_organization_monitor, watchers
):
    user = create_user(
        triggered_urgent_organization_monitor.organization, email='user@heylaika.com'
    )
    watcher_list = triggered_urgent_organization_monitor.watcher_list
    watcher_list.users.set(watchers + [user])
    reconcile_action_items(triggered_urgent_organization_monitor)
    assert find_pending_action_items(triggered_urgent_organization_monitor).count() == 2


@pytest.mark.functional
def test_delete_action_item_when_user_is_removed_from_watcher_list(
    triggered_urgent_organization_monitor, watchers
):
    watcher_list = triggered_urgent_organization_monitor.watcher_list
    watcher_list.users.set(watchers)
    reconcile_action_items(triggered_urgent_organization_monitor)
    action_items = find_pending_action_items(triggered_urgent_organization_monitor)
    assert action_items.count() == 1
    watcher_list.users.set([])
    reconcile_action_items(triggered_urgent_organization_monitor)
    assert action_items.count() == 0


@pytest.mark.functional
def test_reconcile_create_multiple_task(
    second_organization_monitor, organization_monitor, watchers
):
    second_organization_monitor.status = TRIGGERED
    second_organization_monitor.monitor.urgency = URGENCY_STANDARD
    organization_monitor.status = TRIGGERED
    organization_monitor.monitor.urgency = URGENCY_STANDARD

    organization_monitor.watcher_list.users.set(watchers)
    second_organization_monitor.watcher_list.users.set(watchers)

    reconcile_action_items(organization_monitor)
    reconcile_action_items(second_organization_monitor)
    assert UserTask.objects.filter(
        organization_monitor=organization_monitor, status=UserTaskStatus.NOT_STARTED
    ).exists()
