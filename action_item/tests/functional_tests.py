from datetime import datetime

import pytest

from action_item.models import ActionItem, ActionItemStatus
from control.tests import create_control
from user.tests import create_user

CUSTOM_1 = 'XX-C-001'
CUSTOM_2 = 'XX-C-002'
CUSTOM_3 = 'XX-C-003'
RECURRENT_1 = 'XX-R-001'
RECURRENT_PREFIX = 'XX-R'


@pytest.fixture
def users(graphql_organization):
    return [
        create_user(graphql_organization, [], 'johndoe@heylaika.com'),
        create_user(graphql_organization, [], 'johndoe+2@heylaika.com'),
    ]


def _create_action_items(users, is_shared=False, steps=[]):
    data = {
        'name': 'My action item',
        'description': 'Custom Description',
        'due_date': datetime.today(),
        'users': users,
        'steps': steps,
    }
    action_items = (
        [ActionItem.objects.create_shared_action_item(**data)]
        if is_shared
        else ActionItem.objects.create_action_items(**data)
    )

    return action_items


@pytest.mark.functional()
def test_create_action_item_with_new_status(users):
    action_items = _create_action_items(users)

    assert ActionItemStatus.NEW == action_items[0].status


@pytest.mark.functional()
def test_create_action_item_for_a_user(users):
    first_user, _ = users
    _ = _create_action_items([first_user])

    expected_action_items_count = 1
    actual = ActionItem.objects.filter(assignees=first_user)

    assert expected_action_items_count == actual.count()


@pytest.mark.functional()
def test_create_different_action_item_for_every_user(users):
    _create_action_items(users)

    expected_action_items_count = 2
    actual = ActionItem.objects.filter(assignees__in=users)

    assert expected_action_items_count == actual.count()


@pytest.mark.functional()
def test_create_shared_action_item_between_users(users):
    _create_action_items(users, is_shared=True)

    expected_action_items_count = 2
    actual = ActionItem.objects.filter(assignees__in=users)

    assert expected_action_items_count == actual.count()


@pytest.mark.functional()
def test_complete_action_item(users):
    action_items = _create_action_items(users=[users[0]])
    first_action_item = action_items[0]

    first_action_item.complete()

    assert ActionItemStatus.COMPLETED == first_action_item.status


@pytest.mark.functional()
def test_create_action_item_with_multiple_steps(users):
    steps = [
        {
            'name': 'step 1',
            'description': 'step 1 description',
            'due_date': datetime.today(),
        },
        {
            'name': 'step 2',
            'description': 'step 2 description',
            'due_date': datetime.today(),
        },
    ]
    action_items = _create_action_items(users=[users[0]], steps=steps)
    parent_action_item = action_items[0]

    expected_steps_count = 2
    actual = parent_action_item.steps.all().count()

    assert expected_steps_count == actual


@pytest.mark.functional
def test_get_next_index_default(graphql_organization):
    assert CUSTOM_1 == ActionItem.objects.get_next_index(graphql_organization)


@pytest.mark.functional()
def test_get_next_index_prefix(graphql_organization):
    assert RECURRENT_1 == ActionItem.objects.get_next_index(
        graphql_organization, RECURRENT_PREFIX
    )


@pytest.mark.functional()
def test_get_next_index_increment(graphql_organization, users):
    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        status='IMPLEMENTED',
    )

    assert CUSTOM_1 == ActionItem.objects.get_next_index(graphql_organization)

    action_item = ActionItem.objects.create_shared_action_item(
        users=users,
        name='Short name for XX-C-001',
        description='Custom Description',
        due_date=datetime.today(),
        metadata=dict(
            referenceId=CUSTOM_1, organizationId=str(graphql_organization.id)
        ),
    )
    control.action_items.add(action_item)

    assert CUSTOM_2 == ActionItem.objects.get_next_index(graphql_organization)


@pytest.mark.functional()
def test_get_next_index_multiple_controls(graphql_organization, users):
    control1 = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test 1',
        status='IMPLEMENTED',
    )
    action_item1 = ActionItem.objects.create_shared_action_item(
        name=CUSTOM_1,
        description='Custom Description',
        due_date=datetime.today(),
        metadata=dict(referenceId=CUSTOM_1),
        users=users,
    )
    control1.action_items.add(action_item1)

    control2 = create_control(
        organization=graphql_organization,
        display_id=2,
        name='Control Test 2',
        status='IMPLEMENTED',
    )
    action_item2 = ActionItem.objects.create_shared_action_item(
        name=CUSTOM_2,
        description='Custom Description',
        due_date=datetime.today(),
        metadata=dict(referenceId=CUSTOM_2),
        users=users,
    )
    control2.action_items.add(action_item2)

    assert CUSTOM_3 == ActionItem.objects.get_next_index(graphql_organization)


@pytest.mark.django_db
def test_create_and_save_action_item_with_default_recurrent_schedule():
    not_recurrent_action_item = ActionItem.objects.create(name='Not Recurrent AI')
    not_recurrent_action_item.save()

    assert not_recurrent_action_item.recurrent_schedule == ''
    assert not_recurrent_action_item.is_recurrent is False
