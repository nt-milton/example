from datetime import date

from action_item.constants import USER_DEFAULT_TASK, USER_TASKS_BY_ROLE
from action_item.models import ActionItem
from user.models import User


def create_quickstart_action_items(user: User) -> None:
    """
    Creates tasks by role.
    If the task is not defined in the role returns. Otherwise use bulk_create
    to create at once.
    """
    if user.role not in USER_TASKS_BY_ROLE.keys():
        return

    for task_name in USER_TASKS_BY_ROLE.get(user.role, []):
        metadata = {
            'referenceUrl': '',
            'seen': False,
        }
        default_task = USER_DEFAULT_TASK.get(task_name, {})
        metadata.update(default_task)
        subtype = str(default_task.get("subtype", ""))
        action_item = ActionItem(
            name=f'{default_task.get("description", "")} - {user.get_full_name()}',
            metadata=metadata,
            due_date=date.today(),
            description=(
                f'{subtype.capitalize()} subtask due in '
                f'{default_task.get("description", "")}'
            ),
        )
        action_item.save()
        action_item.assignees.add(user)
