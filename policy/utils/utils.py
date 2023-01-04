from datetime import date, timedelta
from typing import List

from django.db.models import Q
from django.db.models.expressions import RawSQL

import evidence.constants as constants
from action_item.constants import TYPE_POLICY
from action_item.models import ActionItem, ActionItemStatus
from laika.utils.order_by import get_order_query
from laika.utils.zip import add_file_to_zip
from policy.models import Policy
from policy.views import get_published_policy_pdf
from user.models import User


def zip_policy(evidence, zip_folder):
    if evidence.type == constants.POLICY:
        add_file_to_zip(
            evidence.name, get_published_policy_pdf(evidence.policy_id), zip_folder
        )


def create_policy_action_items_by_users(users: List[User], policy: Policy) -> None:
    if not users:
        return

    actions_items = []
    update_users = []
    published_policy = policy.versions.last()
    for user in users:
        action_item = ActionItem(
            name=policy.name,
            metadata={
                'seen': False,
                'type': TYPE_POLICY,
                'publishedPolicy': str(published_policy.id),
                'policy': str(policy.id),
            },
            due_date=date.today() + timedelta(days=1),
            description=policy.description,
        )
        action_item.save()
        action_item.assignees.add(user)
        actions_items.append(action_item)
        user.policies_reviewed = False
        user.compliant_completed = False
        update_users.append(user)
    policy.action_items.add(*actions_items)
    User.objects.bulk_update(update_users, ['policies_reviewed', 'compliant_completed'])


def create_policy_action_items(user: User) -> None:
    policies = Policy.objects.filter(
        organization=user.organization, is_required=True, is_published=True
    )
    for policy in policies:
        create_policy_action_items_by_users([user], policy)


def update_action_items_by_policy(policy: Policy) -> None:
    published_policy_id = f'"{policy.versions.last().id}"'
    policy.action_items.filter(metadata__seen=False).update(
        due_date=date.today() + timedelta(days=1),
        metadata=RawSQL(
            """jsonb_set(metadata, '{"publishedPolicy"}', %s, false)""",
            [published_policy_id],
        ),
    )


def are_policies_completed_by_user(user: User) -> bool:
    filters = {'metadata__type': TYPE_POLICY, 'assignees': user}

    return (
        ActionItem.objects.filter(**filters).count()
        <= ActionItem.objects.filter(
            **filters, status=ActionItemStatus.COMPLETED
        ).count()
    )


def get_policy_order_by_query(kwargs):
    order_by = kwargs.get('order_by', {'field': 'display_id', 'order': 'ascend'})
    field = order_by.get('field')
    order = order_by.get('order')
    order_query = get_order_query(field, order)

    return order_query


def create_or_delete_action_items_by_policy(policy: Policy) -> None:
    if policy.is_required:
        users = policy.organization.get_users(
            only_laika_users=True, exclude_super_admin=True
        ).exclude(
            action_items__metadata__policy=str(policy.id),
            action_items__metadata__type=TYPE_POLICY,
        )
        create_policy_action_items_by_users(list(users), policy)
    else:
        policy.action_items.filter(~Q(status=ActionItemStatus.COMPLETED)).delete()
