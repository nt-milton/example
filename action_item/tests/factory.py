from action_item.models import ActionItem
from evidence.models import Evidence


def create_action_item(name, description, due_date, control, user):
    action_item = ActionItem.objects.create(
        name=name,
        description=description,
        due_date=due_date,
        control=control,
        user=user,
    )
    return action_item


def create_action_item_evidence(action_item, name, organization, description=''):
    evidence = Evidence.objects.create(
        name=name, description=description, type='FILE', organization=organization
    )
    action_item.evidences.add(evidence)
    return evidence
