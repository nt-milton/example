import pytest
from django.utils.timezone import now

from action_item.models import ActionItem
from control.constants import (
    ALL_ACTION_ITEMS,
    MAX_OWNER_LIMIT_PER_CONTROL,
    UNASSIGNED_ACTION_ITEMS,
)
from control.models import Control, ControlGroup, ControlPillar, RoadMap
from control.tests import create_control
from control.tests.factory import create_action_item
from control.tests.functional_tests import TEST_CONTROL_DESCRIPTION
from control.tests.mutations import UPDATE_CONTROL_FAMILY_OWNER, UPDATE_CONTROL_OWNERS
from user.constants import ROLE_SUPER_ADMIN
from user.tests import create_user


@pytest.fixture(name="_control_groups")
def fixture_control_groups(graphql_organization):
    roadmap, _ = RoadMap.objects.get_or_create(organization=graphql_organization)
    control_group_1, _ = ControlGroup.objects.get_or_create(
        roadmap=roadmap, name='Milestone 1'
    )
    control_group_2, _ = ControlGroup.objects.get_or_create(
        roadmap=roadmap, name='Milestone 2'
    )
    return control_group_1, control_group_2


@pytest.fixture(name="_controls")
def fixture_controls(graphql_organization):
    control_pillar_1, _ = ControlPillar.objects.get_or_create(name='Asset Management')
    control_pillar_2, _ = ControlPillar.objects.get_or_create(name='Risk Management')

    control_1 = Control.objects.create(
        organization=graphql_organization,
        name='Control test 1',
        pillar=control_pillar_1,
    )
    control_2 = Control.objects.create(
        organization=graphql_organization,
        name='Control test 2',
        pillar=control_pillar_1,
    )
    control_3 = Control.objects.create(
        organization=graphql_organization,
        name='Control test 3',
        pillar=control_pillar_2,
    )

    return control_1, control_2, control_3


@pytest.fixture(name="_control")
def fixture_control(graphql_organization):
    return create_control(
        organization=graphql_organization,
        reference_id="AMG-001",
        display_id=1,
        name='Control Test',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='',
    )


@pytest.fixture(name="_action_item")
def fixture_action_item():
    return create_action_item(
        name="LAI-001",
        description="Action item description",
        completion_date=now(),
        status="new",
        due_date=now(),
        is_required=False,
        is_recurrent=False,
        recurrent_schedule="monthly",
        metadata={'isCustom': True},
    )


@pytest.fixture(name="_action_item_1")
def fixture_action_item_1():
    return create_action_item(
        name="LAI-001",
        description="Action item description",
        completion_date=now(),
        status="new",
        due_date=now(),
        is_required=False,
        is_recurrent=False,
        recurrent_schedule="monthly",
        metadata={'isCustom': True},
    )


@pytest.fixture(name="_action_item_2")
def fixture_action_item_2():
    return create_action_item(
        name="LAI-004",
        description="Action item description",
        completion_date=now(),
        status="new",
        due_date=now(),
        is_required=False,
        is_recurrent=False,
        recurrent_schedule="monthly",
        metadata={'isCustom': True},
    )


@pytest.fixture(name="_action_item_completed")
def fixture_action_item_completed():
    return create_action_item(
        name="LAI-002",
        description="Action item description",
        completion_date=now(),
        status="completed",
        due_date=now(),
        is_required=False,
        is_recurrent=False,
        recurrent_schedule="monthly",
        metadata={'isCustom': True},
    )


@pytest.fixture(name="_action_item_not_applicable")
def fixture_action_item_not_applicable():
    return create_action_item(
        name="LAI-003",
        description="Action item description",
        completion_date=now(),
        status="not_applicable",
        due_date=now(),
        is_required=False,
        is_recurrent=False,
        recurrent_schedule="monthly",
        metadata={'isCustom': True},
    )


def build_custom_user(organization, email):
    return create_user(
        organization, email=email, role=ROLE_SUPER_ADMIN, first_name='john'
    )


@pytest.mark.parametrize(
    'owners_email',
    [
        [],
        ['jhon@heylaika.com'],
        ['jhon@heylaika.com', 'laika@heylaika.com'],
        ['jhon@heylaika.com', 'laika@heylaika.com', 'juan@heylaika.com'],
    ],
)
@pytest.mark.functional(permissions=['control.change_control'])
def test_update_owners_with_valid_values(
    graphql_client, graphql_organization, owners_email
):
    for owner_email in owners_email:
        build_custom_user(graphql_organization, owner_email)

    expect = owners_email

    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description='We have a description',
        owners=expect,
    )

    variables = {'input': {'id': str(control.id), 'ownerEmails': expect}}

    response = graphql_client.execute(UPDATE_CONTROL_OWNERS, variables=variables)
    data = dict(response['data']['updateControl']['data'])
    actual = data['ownerDetails']

    for indx, owner_email in enumerate(expect):
        assert actual[indx]['email'] == owner_email

    assert len(actual) == len(expect)


@pytest.mark.functional(permissions=['control.change_control'])
def test_update_owners_deleting_one_user(graphql_client, graphql_organization):
    build_custom_user(graphql_organization, 'jhon@heylaika.com')
    build_custom_user(graphql_organization, 'laika@heylaika.com')

    expect = 'jhon@heylaika.com'

    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description='We have a description',
        owners=['jhon@heylaika.com', 'laika@heylaika.com'],
    )

    variables = {'input': {'id': str(control.id), 'ownerEmails': [expect]}}

    response = graphql_client.execute(UPDATE_CONTROL_OWNERS, variables=variables)
    data = dict(response['data']['updateControl']['data'])
    actual = data['ownerDetails']
    assert actual[0]['email'] == expect
    assert len(actual) == 1


@pytest.mark.functional(permissions=['control.change_control'])
def test_update_owners_send_valid_value_not_array(graphql_client, graphql_organization):
    build_custom_user(graphql_organization, 'jhon@heylaika.com')

    expect = 'jhon@heylaika.com'

    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description='We have a description',
        owners=[expect],
    )

    variables = {'input': {'id': str(control.id), 'ownerEmails': expect}}

    response = graphql_client.execute(UPDATE_CONTROL_OWNERS, variables=variables)
    data = dict(response['data']['updateControl']['data'])
    actual = data['ownerDetails']
    assert actual[0]['email'] == expect
    assert len(actual) == 1


@pytest.mark.functional(permissions=['control.change_control'])
def test_update_owners_send_invalid_value_in_array(
    graphql_client, graphql_organization
):
    build_custom_user(graphql_organization, 'jhon@heylaika.com')
    build_custom_user(graphql_organization, 'laika@heylaika.com')

    owner_emails = ['jhon@heylaika.com', '']

    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description='We have a description',
        owners=['jhon@heylaika.com', 'laika@heylaika.com'],
    )

    variables = {'input': {'id': str(control.id), 'ownerEmails': owner_emails}}

    response = graphql_client.execute(UPDATE_CONTROL_OWNERS, variables=variables)
    data = dict(response['errors'][0])
    actual = data['message']
    expect = 'The owner email can not be an empty string'
    assert actual == expect


@pytest.mark.functional(permissions=['control.change_control'])
def test_update_owners_send_invalid_value(graphql_client, graphql_organization):
    build_custom_user(graphql_organization, 'jhon@heylaika.com')
    build_custom_user(graphql_organization, 'laika@heylaika.com')

    owner_emails = ''

    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description='We have a description',
        owners=['jhon@heylaika.com', 'laika@heylaika.com'],
    )

    variables = {'input': {'id': str(control.id), 'ownerEmails': owner_emails}}

    response = graphql_client.execute(UPDATE_CONTROL_OWNERS, variables=variables)
    data = dict(response['errors'][0])
    actual = data['message']
    expect = 'The owner email can not be an empty string'
    assert actual == expect


@pytest.mark.functional(permissions=['control.change_control'])
def test_update_owners_more_users_that_allowed(graphql_client, graphql_organization):
    build_custom_user(graphql_organization, 'jhon@heylaika.com')
    build_custom_user(graphql_organization, 'laika@heylaika.com')
    build_custom_user(graphql_organization, 'juan@heylaika.com')
    build_custom_user(graphql_organization, 'anotherjuan@heylaika.com')

    owner_emails = [
        'jhon@heylaika.com',
        'laika@heylaika.com',
        'juan@heylaika.com',
        'anotherjuan@heylaika.com',
    ]

    control = create_control(
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description='We have a description',
        owners=['jhon@heylaika.com', 'laika@heylaika.com', 'juan@heylaika.com'],
    )

    variables = {'input': {'id': str(control.id), 'ownerEmails': owner_emails}}

    response = graphql_client.execute(UPDATE_CONTROL_OWNERS, variables=variables)
    data = dict(response['errors'][0])
    actual = data['message']
    expect = f'Maximum owners allowed is: {MAX_OWNER_LIMIT_PER_CONTROL}'
    assert actual == expect


@pytest.mark.functional(
    permissions=['action_item.view_actionitem', 'control.change_control']
)
def test_update_control_owner_not_action_items_owner(
    graphql_client, graphql_organization, _control, _action_item
):
    _control.action_items.add(_action_item)
    build_custom_user(graphql_organization, 'jhon@heylaika.com')

    graphql_client.execute(
        UPDATE_CONTROL_OWNERS,
        variables={
            'input': {'id': str(_control.id), 'ownerEmails': ['jhon@heylaika.com']}
        },
    )

    control = Control.objects.first()
    assert control.owner1.email == 'jhon@heylaika.com'
    assert control.action_items.count() == 1
    assert control.action_items.first().assignees.count() == 0


@pytest.mark.functional(
    permissions=['action_item.view_actionitem', 'control.change_control']
)
def test_update_control_action_owner_and_override_unassigned_action_items(
    graphql_client, graphql_organization, _control, _action_item, _action_item_1
):
    build_custom_user(graphql_organization, 'jhon@heylaika.com')
    user_1 = build_custom_user(graphql_organization, 'norman@heylaika.com')
    _action_item_1.assignees.add(user_1)
    _control.action_items.add(_action_item, _action_item_1)

    graphql_client.execute(
        UPDATE_CONTROL_OWNERS,
        variables={
            'input': {
                'id': str(_control.id),
                'ownerEmails': ['jhon@heylaika.com'],
                'actionItemsOverrideOption': UNASSIGNED_ACTION_ITEMS,
            }
        },
    )

    action_items = ActionItem.objects.filter(controls=_control)
    action_items_without_assignee = action_items.filter(assignees=None)

    # Check that all action items have been assigned
    assert action_items_without_assignee.count() == 0
    # Check that action items associated with control are 2
    assert action_items.count() == 2
    # Check that action item assignee was just assigned to _action_item_1
    # and it is left the same for _action_item
    assert action_items.first().assignees.first().email == 'jhon@heylaika.com'
    assert action_items.last().assignees.first().email == 'norman@heylaika.com'


@pytest.mark.functional(
    permissions=['action_item.view_actionitem', 'control.change_control']
)
def test_update_control_action_owner_and_override_all_action_items(
    graphql_client,
    graphql_organization,
    _control,
    _action_item,
    _action_item_1,
    _action_item_completed,
    _action_item_not_applicable,
):
    build_custom_user(graphql_organization, 'jhon@heylaika.com')
    user_1 = build_custom_user(graphql_organization, 'norman@heylaika.com')
    _action_item_1.assignees.add(user_1)
    _action_item_completed.assignees.add(user_1)
    _action_item_not_applicable.assignees.add(user_1)
    _control.action_items.add(
        _action_item,
        _action_item_1,
        _action_item_completed,
        _action_item_not_applicable,
    )

    graphql_client.execute(
        UPDATE_CONTROL_OWNERS,
        variables={
            'input': {
                'id': str(_control.id),
                'ownerEmails': ['jhon@heylaika.com'],
                'actionItemsOverrideOption': ALL_ACTION_ITEMS,
            }
        },
    )

    action_items = ActionItem.objects.filter(controls=_control)
    action_items_without_assignee = action_items.filter(assignees=None)

    # Check that all action items have been assigned
    assert action_items_without_assignee.count() == 0
    # Check that action items associated with control are 2
    assert action_items.count() == 4
    # Check that both action items assignee email is same
    # overriding the action item assignee for action_item_1
    assert action_items[0].assignees.first().email == 'jhon@heylaika.com'
    assert action_items[1].assignees.first().email == 'jhon@heylaika.com'
    # Check that action items completed or not_applicable
    # are not updated when control owner is updated
    assert action_items[2].assignees.first().email == 'norman@heylaika.com'
    assert action_items[3].assignees.first().email == 'norman@heylaika.com'


@pytest.mark.functional(permissions=['control.change_control'])
def test_update_control_family_owner(
    graphql_client,
    graphql_organization,
    _controls,
    _action_item_1,
    _action_item_completed,
    _action_item_not_applicable,
):
    control_1, control_2, control_3 = _controls
    user = build_custom_user(graphql_organization, 'jhon@heylaika.com')
    user_1 = build_custom_user(graphql_organization, 'norman@heylaika.com')
    # Assign user_1 to control_1 and control_3 owner and leave
    # control_2 without owner
    control_1.owner1 = user_1
    control_1.save()
    control_3.owner1 = user_1
    control_3.save()

    # Assign action items to control_1 and assign to user_1
    # completed and not applicable action items
    _action_item_1.assignees.add(user_1)
    _action_item_completed.assignees.add(user_1)
    _action_item_not_applicable.assignees.add(user_1)
    control_1.action_items.add(
        _action_item_1, _action_item_completed, _action_item_not_applicable
    )

    input = {'controlFamilyId': str(control_1.pillar.id), 'ownerEmail': user.email}

    response = graphql_client.execute(
        UPDATE_CONTROL_FAMILY_OWNER, variables={'input': input}
    )

    response['data']['updateControlFamilyOwner']['controlFamilyId']

    controls = Control.objects.all().order_by('name')
    action_items = controls.first().action_items.all()

    # Checks that control_1 and control_2 have changed user
    # but control_3 that belongs to another family remains with same owner
    assert controls[0].owner1.email == 'jhon@heylaika.com'
    assert controls[1].owner1.email == 'jhon@heylaika.com'
    assert controls[2].owner1.email == 'norman@heylaika.com'
    # Checks that first action item associated to first control has
    # jhon@heylaika.com as assignee
    assert action_items[0].assignees.first().email == 'jhon@heylaika.com'
    # # Checks that completed and not applicable action items keep the
    # # old assignee
    assert action_items[1].assignees.first().email == 'norman@heylaika.com'
    assert action_items[2].assignees.first().email == 'norman@heylaika.com'


@pytest.mark.functional(permissions=['control.change_control'])
def test_update_control_family_owner_by_group(
    graphql_client,
    graphql_organization,
    _controls,
    _action_item_1,
    _action_item_2,
    _action_item_completed,
    _action_item_not_applicable,
    _control_groups,
):
    control_1, control_2, control_3 = _controls
    control_group_1, control_group_2 = _control_groups
    user = build_custom_user(graphql_organization, 'jhon@heylaika.com')
    user_1 = build_custom_user(graphql_organization, 'norman@heylaika.com')
    # Assign user_1 to control_1 and control_3 owner and leave
    # control_2 without owner
    control_1.owner1 = user_1
    control_1.save()
    control_3.owner1 = user_1
    control_3.save()

    # Assign control_group_1 to control_1 and
    # control_group_2 to control_2 and control_3
    control_group_1.controls.add(control_1)
    control_group_2.controls.add(control_2, control_3)

    # Assign action items to control_1 and
    # assign to action items assignee as user_1
    # completed and not applicable action items
    _action_item_1.assignees.add(user_1)
    _action_item_completed.assignees.add(user_1)
    _action_item_not_applicable.assignees.add(user_1)
    control_1.action_items.add(
        _action_item_1, _action_item_completed, _action_item_not_applicable
    )
    control_2.action_items.add(_action_item_2)

    input = {
        'controlFamilyId': str(control_1.pillar.id),
        'ownerEmail': user.email,
        'groupId': str(control_group_1.id),
    }

    graphql_client.execute(UPDATE_CONTROL_FAMILY_OWNER, variables={'input': input})

    control_1 = Control.objects.get(id=control_1.id)
    control_2 = Control.objects.get(id=control_2.id)
    control_3 = Control.objects.get(id=control_3.id)

    action_item_new = ActionItem.objects.get(id=_action_item_1.id)
    action_item_completed = ActionItem.objects.get(id=_action_item_completed.id)
    action_item_not_applicable = ActionItem.objects.get(
        id=_action_item_not_applicable.id
    )

    control_2_action_items = control_2.action_items.all()

    # Checks that control_1 have changed user
    # but control_2 that belongs to same group but another milestone and
    # control_3 that belongs to another family remains with same owner
    assert control_1.owner1.email == 'jhon@heylaika.com'
    assert control_2.owner1 is None
    assert control_3.owner1.email == 'norman@heylaika.com'
    # Checks that first action item associated to first control has
    # jhon@heylaika.com as assignee
    assert action_item_new.assignees.first().email == 'jhon@heylaika.com'
    # Checks that completed and not applicable action items keep the
    # old assignee
    assert action_item_completed.assignees.first().email == 'norman@heylaika.com'
    assert action_item_not_applicable.assignees.first().email == 'norman@heylaika.com'
    # check that action items that belong to control_2
    # have not changed assignees
    for ai in control_2_action_items:
        assert ai.assignees.exists() is False
