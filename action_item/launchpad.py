from laika.utils.dates import format_iso_date
from search.types import CmdKActionItemResultType


def format_due_date(due_date):
    if due_date:
        return format_iso_date(due_date, '%m/%d/%Y')

    return None


def launchpad_mapper(model, organization_id):
    action_items = model.objects.filter(
        controls__organization_id=organization_id
    ).values(
        'id',
        'name',
        'description',
        'controls__id',
        'controls__reference_id',
        'metadata',
        'due_date',
    )

    return [
        CmdKActionItemResultType(
            id=f"{action_item['controls__id']}-{action_item['id']}",
            name=action_item['name'],
            description=action_item['description'],
            control=action_item['controls__reference_id'],
            reference_id=action_item['metadata'].get('referenceId'),
            due_date=format_due_date(action_item['due_date']),
            url=f"/controls/{action_item['controls__id']}",
        )
        for action_item in action_items
    ]
