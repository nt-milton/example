import json
from datetime import datetime, timedelta, timezone

import pytest

from action_item.constants import TYPE_ACCESS_REVIEW
from action_item.models import ActionItem as MyComplianceActionItem
from dashboard.models import UserTaskStatus
from dashboard.tasks import (
    send_pending_action_items_by_user_email,
    send_pending_action_items_daily_by_organization,
    send_pending_action_items_weekly_by_organization,
)
from dashboard.templatetags.action_items_render import action_items_render, due_date
from dashboard.tests.factory import (
    create_dashboard_action_item,
    create_subtask,
    create_subtask_action_item,
)
from dashboard.tests.mutations import UPDATE_DASHBOARD_ACTION_ITEM
from dashboard.tests.queries import (
    GET_DASHBOARD_ITEMS,
    GET_FRAMEWORK_CARDS,
    GET_TASK_VIEW_ITEMS,
)
from user.constants import USER_ROLES

NOT_STARTED = 'not_started'
COMPLETED = 'completed'
IN_PROGRESS = 'in_progress'
PENDING_ITEM_DESCRIPTION = 'Pending action item'
COMPLETED_ITEM_DESCRIPTION = 'Completed action item'
PENDING = 'pending'
NEW = 'new'


def get_graph_query_action_items_executed(graphql_client, filters={}, status='pending'):
    return graphql_client.execute(
        GET_DASHBOARD_ITEMS,
        variables={
            'pagination': dict(page=1, pageSize=10),
            'filter': json.dumps({"user": True, **filters}),
            'actionItemsStatus': status,
        },
    )


def get_graph_query_task_view_action_items_executed(
    graphql_client, filters={}, status='pending'
):
    return graphql_client.execute(
        GET_TASK_VIEW_ITEMS,
        variables={
            'filter': json.dumps({"user": True, **filters}),
            'actionItemsStatus': status,
        },
    )


@pytest.mark.functional
def test_send_emails_for_not_started_status_weekly(
    graphql_organization, pending_subtask_weekly
):
    result = send_pending_action_items_weekly_by_organization.delay(
        graphql_organization.id
    )
    assert result.get() == {graphql_organization.name: 1}


@pytest.mark.functional
def test_send_emails_for_completed_status_weekly(
    graphql_organization, completed_subtask_weekly
):
    result = send_pending_action_items_weekly_by_organization.delay(
        graphql_organization.id
    )
    assert result.get() == {graphql_organization.name: 0}


@pytest.mark.functional
def test_send_emails_for_not_started_status_daily(
    graphql_organization, pending_subtask_daily
):
    result = send_pending_action_items_daily_by_organization.delay(
        graphql_organization.id
    )
    assert result.get() == {graphql_organization.name: 1}


@pytest.mark.functional
def test_send_emails_for_completed_status_daily(
    graphql_organization, completed_subtask_daily
):
    result = send_pending_action_items_daily_by_organization.delay(
        graphql_organization.id
    )
    assert result.get() == {graphql_organization.name: 0}


@pytest.mark.functional
def test_user_without_action_items(user_daily, no_action_items_subtask):
    result = send_pending_action_items_by_user_email.delay(user_daily.email)
    assert result.get() is False


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_dashboard_pending_items_query(
    graphql_client,
    graphql_organization,
    task,
):
    organization, user = graphql_client.context.values()
    subtask = create_subtask(user, task)
    subtask2 = create_subtask(user, task, 'Subtasks Text 2')
    create_subtask_action_item(
        organization, subtask, user, PENDING_ITEM_DESCRIPTION, NOT_STARTED
    )
    create_subtask_action_item(
        organization, subtask2, user, PENDING_ITEM_DESCRIPTION, IN_PROGRESS
    )

    executed = get_graph_query_action_items_executed(graphql_client)
    action_items = executed['data']['actionItems']['data']
    assert len(action_items) == 2
    assert action_items[0]['description'] == PENDING_ITEM_DESCRIPTION
    assert action_items[0]['seen'] is False
    assert action_items[0]['status'] == NOT_STARTED
    assert len(action_items[0]['subtaskText']) > 0
    assert action_items[0]['subtaskText'] == subtask.text
    assert action_items[1]['status'] == IN_PROGRESS


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_dashboard_completed_items_query(
    graphql_client,
    graphql_organization,
    task,
):
    organization, user = graphql_client.context.values()
    subtask = create_subtask(user, task)
    create_subtask_action_item(
        organization, subtask, user, COMPLETED_ITEM_DESCRIPTION, COMPLETED
    )

    executed = get_graph_query_action_items_executed(graphql_client, status='completed')
    action_items = executed['data']['actionItems']['data']
    assert action_items[0]['description'] == COMPLETED_ITEM_DESCRIPTION
    assert action_items[0]['seen'] is True
    assert action_items[0]['status'] == COMPLETED
    assert len(action_items[0]['subtaskText']) > 0
    assert action_items[0]['subtaskText'] == subtask.text


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_change_status_user_task(graphql_client, graphql_user):
    action_item = MyComplianceActionItem(
        name='action item',
        metadata={
            'referenceUrl': '',
            'seen': False,
        },
        description='',
    )
    action_item.save()
    action_item.assignees.add(graphql_user)
    new_date = datetime.now().date().strftime("%Y-%m-%d")
    assert action_item.metadata.get('seen', False) is False
    resp = graphql_client.execute(
        UPDATE_DASHBOARD_ACTION_ITEM,
        variables={'id': str(action_item.id), 'seen': True, 'completionDate': new_date},
    )
    user_task_data = resp['data']['updateDashboardActionItem']
    assert user_task_data['seen']
    assert user_task_data['completionDate'] == new_date
    assert user_task_data['status'] == UserTaskStatus.COMPLETED.value


@pytest.mark.parametrize(
    "input_due_date,expected",
    [
        ("", "due"),
        (datetime.now(tz=timezone.utc), "due today"),
        (datetime.now(tz=timezone.utc) + timedelta(days=1), "due in 1 day"),
        (datetime.now(tz=timezone.utc) + timedelta(days=3), "due in 3 days"),
        (datetime.now(tz=timezone.utc) - timedelta(days=1), "1 day overdue"),
        (datetime.now(tz=timezone.utc) - timedelta(days=7), "7 days overdue"),
    ],
)
def test_due_date_email_string(input_due_date, expected):
    if input_due_date:
        input_due_date = input_due_date.replace(hour=00, minute=00)

    due_str = due_date(input_due_date)

    assert expected in due_str


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_get_framework_cards_with_implemented_controls(
    graphql_client, framework_with_implemented_controls
):
    response = graphql_client.execute(GET_FRAMEWORK_CARDS)
    framework_cards_list = response['data']['frameworkCards']
    framework1 = framework_cards_list[0]
    framework2 = framework_cards_list[1]

    assert framework1['frameworkName'] == 'ISO 27001 (2013)'
    assert framework2['frameworkName'] == 'SOC 2 Security'
    assert framework1['operational'] == 0
    assert framework1['needsAttention'] == 0
    assert framework1['notImplemented'] == 1
    assert framework2['operational'] == 1
    assert framework2['needsAttention'] == 1
    assert framework2['notImplemented'] == 2
    assert framework1['progress'] == 100
    assert framework1['controls'] == 1
    assert framework2['progress'] == 50
    assert framework2['controls'] == 4


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_get_framework_cards_with_not_implemented_controls(
    graphql_client, framework_with_not_implemented_controls
):
    response = graphql_client.execute(GET_FRAMEWORK_CARDS)
    framework_cards_list = response['data']['frameworkCards']
    framework1 = framework_cards_list[0]

    assert framework1['frameworkName'] == 'SOC 2 Type 1'
    assert framework1['operational'] == 0
    assert framework1['needsAttention'] == 0
    assert framework1['notImplemented'] == 2
    assert framework1['progress'] == 0
    assert framework1['controls'] == 2


@pytest.mark.parametrize(
    'user_role, action_item_status, expected_action_items',
    [
        (USER_ROLES['SALESPERSON'], PENDING, 2),
        (USER_ROLES['SALESPERSON'], COMPLETED, 1),
        (USER_ROLES['VIEWER'], PENDING, 2),
        (USER_ROLES['VIEWER'], COMPLETED, 1),
    ],
)
@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_sales_and_viewer_users_action_items(
    user_role,
    action_item_status,
    expected_action_items,
    graphql_client,
    graphql_user,
    action_items_from_all_types,
):
    graphql_user.role = user_role
    graphql_user.save()
    executed = get_graph_query_action_items_executed(
        graphql_client, status=action_item_status
    )
    action_items = executed['data']['actionItems']['data']

    assert len(action_items) == expected_action_items


@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_dashboard_access_review_action_items_query(
    graphql_client, graphql_user, graphql_organization
):
    action_item = create_dashboard_action_item(
        'access-review-action-item-1',
        graphql_user,
        graphql_organization,
        PENDING_ITEM_DESCRIPTION,
        COMPLETED,
        TYPE_ACCESS_REVIEW,
    )
    executed = get_graph_query_action_items_executed(
        graphql_client, status=action_item.status
    )
    action_item = executed['data']['actionItems']['data'][0]
    assert action_item['type'] == 'Access Review'
    assert action_item['group'] == 'group'


@pytest.mark.functional
def test_action_items_render(graphql_user, graphql_organization):
    action_item = MyComplianceActionItem.objects.create(
        name='name', description='description', metadata={'type': 'access_review'}
    )
    assert 'wifi-tethering.png' in action_items_render(action_item)


# My Compliance view action items tests


@pytest.mark.parametrize(
    'user_role, action_item_status, expected_action_items',
    [
        (USER_ROLES['SALESPERSON'], PENDING, 2),
        (USER_ROLES['SALESPERSON'], COMPLETED, 1),
        (USER_ROLES['VIEWER'], PENDING, 2),
        (USER_ROLES['VIEWER'], COMPLETED, 1),
    ],
)
@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_sales_and_viewer_users_my_compliance_action_items(
    user_role,
    action_item_status,
    expected_action_items,
    graphql_client,
    graphql_user,
    task_view_action_items_from_all_types,
):
    graphql_user.role = user_role
    graphql_user.save()
    executed = get_graph_query_task_view_action_items_executed(
        graphql_client, status=action_item_status
    )
    action_items = executed['data']['taskViewActionItems']['data']

    assert len(action_items) == expected_action_items


@pytest.mark.parametrize(
    'framework_code, expected_action_items', [('SOC', 4), ('ISO', 3), ('SOC-C', 3)]
)
@pytest.mark.functional(permissions=['dashboard.view_dashboard'])
def test_my_compliance_action_items_filtered_by_framework(
    framework_code,
    expected_action_items,
    graphql_client,
    graphql_user,
    task_view_action_items_from_all_types,
):
    # The expected action items are the count of
    # both control action items that belong to the
    # selected framework and the other types of action
    # items that aren't link to it.
    executed = get_graph_query_task_view_action_items_executed(
        graphql_client, filters={"framework": framework_code}
    )
    action_items = executed['data']['taskViewActionItems']['data']

    assert len(action_items) == expected_action_items
