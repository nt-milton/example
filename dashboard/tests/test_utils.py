import pytest

from action_item.constants import (
    TYPE_ACCESS_REVIEW,
    TYPE_CONTROL,
    TYPE_POLICY,
    TYPE_QUICK_START,
)
from action_item.models import ActionItem
from dashboard.constants import MONITOR_DASHBOARD_TASK_TYPE
from dashboard.tests.factory import create_dashboard_task, create_dashboard_user_task
from dashboard.utils import (
    get_dashboard_action_item_metadata,
    get_dashboard_action_item_subtype,
    get_dashboard_action_item_type,
)

EMPTY_UNIQUE_ACTION_ITEM_ID = EMPTY_SUBTYPE = EMPTY_MODEL_ID = ''
EMPTY_METADATA = {}


@pytest.fixture()
def dashboard_task():
    return create_dashboard_task(
        name='dashboard task',
        task_type=MONITOR_DASHBOARD_TASK_TYPE,
        task_subtype='monitor',
        metadata={},
    )


@pytest.fixture()
def dashboard_user_task(graphql_organization, graphql_user, dashboard_task):
    return create_dashboard_user_task(
        organization=graphql_organization, assignee=graphql_user, task=dashboard_task
    )


@pytest.mark.parametrize(
    'action_item_type, human_readable_action_item_type',
    [
        ('playbook_task', 'Playbook Task'),
        (TYPE_ACCESS_REVIEW, 'Access Review'),
        (TYPE_CONTROL, 'control'),
        (TYPE_POLICY, 'policy'),
        (MONITOR_DASHBOARD_TASK_TYPE, 'Monitor'),
        (TYPE_QUICK_START, 'Quick Start'),
    ],
)
def test_get_dashboard_action_item_type(
    action_item_type, human_readable_action_item_type
):
    assert (
        get_dashboard_action_item_type(action_item_type)
        == human_readable_action_item_type
    )


@pytest.mark.django_db
def test_get_dashboard_action_item_monitor_subtype(dashboard_task, dashboard_user_task):
    assert (
        get_dashboard_action_item_subtype(
            MONITOR_DASHBOARD_TASK_TYPE,
            dashboard_user_task.id,
            EMPTY_UNIQUE_ACTION_ITEM_ID,
        )
        == dashboard_task.task_subtype
    )


@pytest.mark.django_db
def test_get_dashboard_action_item_quick_start_subtype(
    graphql_user, graphql_organization
):
    subtype_training = 'training'

    action_item = ActionItem.objects.create(
        metadata={"type": 'quick_start', "subtype": subtype_training},
    )

    action_item.assignees.add(graphql_user)

    assert (
        get_dashboard_action_item_subtype(
            TYPE_QUICK_START, graphql_organization.id, action_item.id
        )
        == subtype_training
    )


@pytest.mark.django_db
def test_get_dashboard_action_item_subtype_empty():
    assert (
        get_dashboard_action_item_subtype(
            TYPE_CONTROL, EMPTY_MODEL_ID, EMPTY_UNIQUE_ACTION_ITEM_ID
        )
        == EMPTY_SUBTYPE
    )
    assert (
        get_dashboard_action_item_subtype(
            TYPE_POLICY, EMPTY_MODEL_ID, EMPTY_UNIQUE_ACTION_ITEM_ID
        )
        == EMPTY_SUBTYPE
    )


@pytest.mark.django_db
def test_get_action_item_metadata_for_monitor_task(dashboard_task, dashboard_user_task):
    assert (
        get_dashboard_action_item_metadata(
            MONITOR_DASHBOARD_TASK_TYPE,
            dashboard_user_task.id,
            EMPTY_UNIQUE_ACTION_ITEM_ID,
        )
        == dashboard_task.metadata
    )


@pytest.mark.django_db
def test_get_action_item_metadata_for_quick_start_action_item(
    graphql_user, graphql_organization
):
    task_metadata = {"test": "test value"}

    action_item = ActionItem.objects.create(
        metadata={"type": 'quick_start', "task_metadata": task_metadata},
    )

    action_item.assignees.add(graphql_user)

    assert get_dashboard_action_item_metadata(
        TYPE_QUICK_START, graphql_organization.id, action_item.id
    ) == action_item.metadata.get('task_metadata')


@pytest.mark.django_db
def test_get_action_item_metadata_for_policy_action_item(
    graphql_user, graphql_organization
):
    action_item = ActionItem.objects.create(
        metadata={"type": 'policy', "test_key": "test_value"},
    )

    action_item.assignees.add(graphql_user)

    assert (
        get_dashboard_action_item_metadata(
            TYPE_POLICY, graphql_organization.id, action_item.id
        )
        == action_item.metadata
    )


@pytest.mark.django_db
def test_get_action_item_metadata_empty_metadata(graphql_user, graphql_organization):
    action_item = ActionItem.objects.create(
        metadata={"type": 'control', "test_key": "test_value"},
    )

    action_item.assignees.add(graphql_user)

    assert (
        get_dashboard_action_item_metadata(
            TYPE_CONTROL, graphql_organization.id, action_item.id
        )
        == EMPTY_METADATA
    )
