from datetime import datetime, timedelta

from dashboard.models import ActionItem as DashboardActionItem
from dashboard.models import Task, TaskView, UserTask
from program.constants import SUBTASK_DOCUMENTATION
from program.models import SubTask


def create_dashboard_user_task(*, organization, assignee, task, **kwargs):
    return UserTask.objects.create(
        organization=organization, assignee=assignee, task=task, **kwargs
    )


def create_dashboard_task(*, name, task_type, task_subtype, **kwargs):
    return Task.objects.create(
        name=name, task_type=task_type, task_subtype=task_subtype, **kwargs
    )


def create_subtask_action_item(
    organization, subtask, user, description, status
) -> DashboardActionItem:
    return DashboardActionItem.objects.create(
        unique_action_item_id=subtask.id,
        organization=organization,
        assignee=user,
        status=status,
        due_date=datetime.now() + timedelta(days=5),
        description=description,
        sort_index=1,
        group=SUBTASK_DOCUMENTATION,
    )


def create_subtask(user, task, subtask_text='SubTask 1'):
    return SubTask.objects.create(
        text=subtask_text,
        assignee=user,
        group='Documentation',
        requires_evidence=True,
        task=task,
        due_date=datetime.now(),
    )


def create_task_view_action_item(
    *, unique_action_item_id, user, organization, description, status, type, **kwargs
) -> TaskView:
    return TaskView.objects.create(
        unique_action_item_id=unique_action_item_id,
        assignee=user,
        organization=organization,
        status=status,
        due_date=datetime.now() + timedelta(days=5),
        description=description,
        sort_index=1,
        group='',
        type=type,
        **kwargs
    )


def create_dashboard_action_item(
    unique_action_item_id, user, organization, description, status, type, **kwargs
) -> DashboardActionItem:
    return DashboardActionItem.objects.create(
        assignee=user,
        unique_action_item_id=unique_action_item_id,
        organization=organization,
        status=status,
        due_date=datetime.now() + timedelta(days=5),
        description=description,
        sort_index=1,
        group='',
        type=type,
        **kwargs
    )
