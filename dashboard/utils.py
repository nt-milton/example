import logging

from action_item.constants import (
    TYPE_ACCESS_REVIEW,
    TYPE_CONTROL,
    TYPE_POLICY,
    TYPE_QUICK_START,
)
from action_item.models import ActionItem
from dashboard.constants import MONITOR_DASHBOARD_TASK_TYPE
from dashboard.models import USER_TASK_TYPES, UserTask

logger = logging.getLogger(__name__)


def get_dashboard_action_item_type(action_item_type: str):
    if action_item_type == 'playbook_task':
        return 'Playbook Task'
    if action_item_type == TYPE_QUICK_START:
        return 'Quick Start'
    if action_item_type == MONITOR_DASHBOARD_TASK_TYPE:
        return 'Monitor'
    if action_item_type == TYPE_ACCESS_REVIEW:
        return 'Access Review'
    if action_item_type in [TYPE_CONTROL, TYPE_POLICY]:
        return action_item_type


def get_dashboard_action_item_subtype(
    action_item_type: str, model_id: str, unique_action_item_id: str
):
    if action_item_type in USER_TASK_TYPES:
        return (
            UserTask.objects.select_related('task').get(id=model_id).task.task_subtype
        )
    if action_item_type == TYPE_QUICK_START:
        return ActionItem.objects.get(id=unique_action_item_id).metadata.get(
            'subtype', ''
        )
    return ''


def get_dashboard_action_item_metadata(
    action_item_type: str, model_id: str, unique_action_item_id: str
):
    if action_item_type in USER_TASK_TYPES:
        return UserTask.objects.select_related('task').get(id=model_id).task.metadata
    if action_item_type in TYPE_QUICK_START:
        return ActionItem.objects.get(id=unique_action_item_id).metadata.get(
            'task_metadata', {}
        )
    if action_item_type in [TYPE_POLICY, TYPE_ACCESS_REVIEW]:
        return ActionItem.objects.get(id=unique_action_item_id).metadata
    return {}
