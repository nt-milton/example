from datetime import date
from uuid import UUID

from action_item.models import ActionItem, ActionItemStatus


def action_item_has_children(action_item: ActionItem) -> bool:
    return action_item and (
        action_item.status == ActionItemStatus.COMPLETED
        or (action_item.due_date and action_item.due_date.date() < date.today())
    )


def get_recurrent_last_action_item(reference_id: str, org_id: UUID) -> ActionItem:
    action_item = (
        ActionItem.objects.filter(
            metadata__referenceId=reference_id, metadata__organizationId=str(org_id)
        )
        .order_by('id')
        .first()
    )
    if action_item_has_children(action_item):
        return get_recurrent_last_child_action_item(action_item, org_id)
    return action_item


def get_recurrent_last_child_action_item(action_item: ActionItem, org_id: UUID):
    child_action_item = (
        ActionItem.objects.filter(
            metadata__organizationId=str(org_id),
            parent_action_item=action_item,
        )
        .exclude(status=ActionItemStatus.COMPLETED)
        .order_by('-id')
        .first()
    )
    return child_action_item
