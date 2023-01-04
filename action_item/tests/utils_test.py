from datetime import datetime

import pytest

from action_item.models import ActionItem, ActionItemStatus
from action_item.utils import get_recurrent_last_action_item
from user.tests import create_user

REFERENCE_ID = 'XX-C-001'
CUSTOM_1 = 'XX-C-002'


@pytest.fixture()
def action_item(graphql_organization):
    user = create_user(
        graphql_organization, email='user1@mail.com', username='test-user-1-username'
    )
    action_item = ActionItem.objects.create_shared_action_item(
        name='action item name',
        description='Custom Description',
        due_date=datetime.today(),
        metadata=dict(
            referenceId=REFERENCE_ID, organizationId=str(graphql_organization.id)
        ),
        users=[user],
    )
    return action_item


@pytest.mark.django_db
def test_get_recurrent_last_action_item(action_item, graphql_organization):
    ActionItem.objects.create_shared_action_item(
        name='action item child 1',
        description='Custom Description',
        due_date=datetime.today(),
        metadata=dict(
            organizationId=str(graphql_organization.id), referenceId=REFERENCE_ID
        ),
        status=ActionItemStatus.NEW,
        parent_action_item=action_item,
    )

    action_item_result = get_recurrent_last_action_item(
        REFERENCE_ID, graphql_organization.id
    )

    assert action_item.id == action_item_result.id


@pytest.mark.django_db
def test_get_recurrent_completed_action_item_with_child(
    action_item, graphql_organization
):
    action_item.status = ActionItemStatus.COMPLETED
    action_item.save()
    ActionItem.objects.create_shared_action_item(
        name='action item child 1',
        description='Custom Description',
        due_date=datetime.today(),
        metadata=dict(
            organizationId=str(graphql_organization.id), referenceId=REFERENCE_ID
        ),
        status=ActionItemStatus.NEW,
        parent_action_item=action_item,
    )
    child_action_item2 = ActionItem.objects.create_shared_action_item(
        name='action item child 2',
        description='Custom Description',
        due_date=datetime.today(),
        metadata=dict(
            organizationId=str(graphql_organization.id), referenceId=REFERENCE_ID
        ),
        status=ActionItemStatus.NEW,
        parent_action_item=action_item,
    )
    action_item_result = get_recurrent_last_action_item(
        REFERENCE_ID, graphql_organization.id
    )
    assert child_action_item2.id == action_item_result.id
