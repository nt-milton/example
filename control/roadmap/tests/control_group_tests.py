import datetime

import pytest
import pytz
from django.db.models import Q
from django.utils import timezone

from action_item.models import ActionItem, ActionItemStatus
from control.models import Control, ControlGroup, RoadMap
from control.roadmap.tests import (
    UPDATE_CONTROL_GROUP,
    UPDATE_CONTROL_GROUP_WEB,
    create_control_group,
    create_roadmap,
)
from control.tests.factory import create_action_item, create_control, get_control
from laika.utils.dates import ISO_8601_FORMAT_WITH_TZ
from organization.tests.factory import create_organization

from ..helpers import get_reference_id
from .factory import get_control_group
from .mutations import (
    CREATE_CONTROL_GROUP,
    DELETE_GROUP,
    MOVE_CONTROLS_TO_CONTROL_GROUP,
    UPDATE_CONTROL_GROUP_SORT_ORDER,
    UPDATE_CONTROL_SORT_ORDER,
)

FIRST_PLACE = 1
SECOND_PLACE = 2
THIRD_PLACE = 3

CONTROL_GROUP_TEST_NAME_1 = 'Group test 1'
CONTROL_GROUP_TEST_NAME_2 = 'Group test 2'

SIMPLE_DATE_FORMAT = '%Y-%m-%d'


@pytest.fixture
def organization():
    return create_organization(name='Laika Dev')


@pytest.fixture
def roadmap(organization):
    return create_roadmap(
        organization=organization,
    )


@pytest.fixture
def control_group(roadmap):
    return create_control_group(
        roadmap=roadmap,
        name='Group test',
        start_date=datetime.date(2022, 6, 9),
        due_date=datetime.date(2022, 7, 9),
    )


@pytest.fixture(name='_control_group_2')
def fixture_control_group_2(roadmap):
    return create_control_group(
        roadmap=roadmap,
        name=CONTROL_GROUP_TEST_NAME_2,
        start_date=datetime.datetime.today() - datetime.timedelta(days=7),
        due_date=datetime.datetime.today(),
    )


@pytest.fixture(name="_controls")
def fixture_controls(graphql_organization, control_group):
    control_1 = Control.objects.create(
        organization=graphql_organization,
        name='Control test 1',
    )
    control_2 = Control.objects.create(
        organization=graphql_organization,
        name='Control test 2',
    )
    control_3 = Control.objects.create(
        organization=graphql_organization, name='Control test 3'
    )

    return control_1, control_2, control_3


@pytest.fixture(name="_action_items")
def fixture_action_items(graphql_organization, _controls):
    action_item_1 = create_action_item(
        name="Action item 1",
        description="Action item description 1",
        status="new",
        is_required=True,
        is_recurrent=False,
        start_date=datetime.datetime.today() - datetime.timedelta(days=7),
        due_date=datetime.date.today(),
        metadata={
            'referenceId': 'CF-C-001',
            'organizationId': str(graphql_organization.id),
        },
    )
    action_item_2 = create_action_item(
        name="Action item 2",
        description="Action item description 1",
        status="completed",
        is_required=True,
        is_recurrent=False,
        start_date=datetime.datetime.today() - datetime.timedelta(days=7),
        due_date=datetime.date.today(),
        metadata={
            'referenceId': 'CF-C-001',
            'organizationId': str(graphql_organization.id),
        },
    )
    action_item_3 = create_action_item(
        name="Action item 3",
        description="Action item description 2",
        status="new",
        is_required=False,
        is_recurrent=False,
        start_date=datetime.datetime.today() - datetime.timedelta(days=7),
        due_date=datetime.date.today(),
        metadata={
            'referenceId': 'CF-C-002',
            'organizationId': str(graphql_organization.id),
        },
    )
    action_item_4 = create_action_item(
        name="Action item 4",
        description="Action item description 3",
        status="completed",
        is_required=True,
        is_recurrent=False,
        start_date=datetime.datetime.today() - datetime.timedelta(days=7),
        due_date=datetime.date.today(),
        metadata={
            'referenceId': 'CF-C-003',
            'organizationId': str(graphql_organization.id),
        },
    )
    action_item_5 = create_action_item(
        name="Action item 5",
        description="Action item shared between controls",
        status="new",
        is_required=True,
        is_recurrent=False,
        start_date=datetime.date.today() - datetime.timedelta(days=8),
        due_date=datetime.date.today() - datetime.timedelta(days=1),
        metadata={
            'referenceId': '00-C-005',
            'organizationId': str(graphql_organization.id),
        },
    )

    return action_item_1, action_item_2, action_item_3, action_item_4, action_item_5


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_control_group_name(graphql_client, control_group):
    expected_name = 'new group name'

    update_group_input = {
        'input': dict(
            id=control_group.id,
            name=expected_name,
        )
    }
    graphql_client.execute(UPDATE_CONTROL_GROUP, variables=update_group_input)
    group = ControlGroup.objects.get(id=control_group.id)
    assert group.name == expected_name


def execute_dates_mutation(
    graphql_client, control_group, mutation, start_date=None, due_date=None
):
    input_dict = dict()
    input_dict.update(id=control_group.id)

    if start_date is not None:
        input_dict.update(
            startDate=datetime.datetime.strptime(start_date, ISO_8601_FORMAT_WITH_TZ)
        )
    if due_date is not None:
        input_dict.update(
            dueDate=datetime.datetime.strptime(due_date, ISO_8601_FORMAT_WITH_TZ)
        )

    update_group_input = {'input': input_dict}
    graphql_client.execute(mutation, variables=update_group_input)


def assert_formatted_date(actual_date, expected_date):
    formatted_expected_date = datetime.datetime.strptime(
        expected_date, ISO_8601_FORMAT_WITH_TZ
    )
    assert actual_date == formatted_expected_date


def execute_update_control_group_by_mutation(graphql_client, control_group, mutation):
    expected_start_date_string = '2020-04-28T00:00:00+00:00'
    expected_due_date_string = '2050-04-28T00:00:00+00:00'

    execute_dates_mutation(
        graphql_client=graphql_client,
        control_group=control_group,
        mutation=mutation,
        start_date=expected_start_date_string,
        due_date=expected_due_date_string,
    )

    group = ControlGroup.objects.get(id=control_group.id)
    assert_formatted_date(group.start_date, expected_start_date_string)
    assert_formatted_date(group.due_date, expected_due_date_string)


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_control_group_dates(graphql_client, control_group):
    execute_update_control_group_by_mutation(
        graphql_client, control_group, UPDATE_CONTROL_GROUP
    )


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_control_group_dates_web(graphql_client, control_group):
    execute_update_control_group_by_mutation(
        graphql_client, control_group, UPDATE_CONTROL_GROUP_WEB
    )


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_control_group_dates_null_start_date(graphql_client, control_group):
    expected_due_date_string = '2050-05-28T00:00:00+00:00'

    execute_dates_mutation(
        graphql_client=graphql_client,
        control_group=control_group,
        mutation=UPDATE_CONTROL_GROUP,
        due_date=expected_due_date_string,
    )

    group = ControlGroup.objects.get(id=control_group.id)

    assert group.start_date is not None
    assert_formatted_date(group.due_date, expected_due_date_string)


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_control_group_dates_null_due_date(graphql_client, control_group):
    expected_start_date_string = '2050-05-28T00:00:00+00:00'

    execute_dates_mutation(
        graphql_client=graphql_client,
        control_group=control_group,
        mutation=UPDATE_CONTROL_GROUP,
        start_date=expected_start_date_string,
    )

    group = ControlGroup.objects.get(id=control_group.id)

    assert_formatted_date(group.start_date, expected_start_date_string)
    assert group.due_date is not None


@pytest.mark.functional(permissions=['control.delete_controlgroup'])
def test_delete_control_group(graphql_client, graphql_organization):
    roadmap = create_roadmap(
        organization=graphql_organization,
    )

    first_control_group = create_control_group(
        roadmap=roadmap,
        name=CONTROL_GROUP_TEST_NAME_1,
        start_date=datetime.date(2021, 6, 9),
        due_date=datetime.date(2021, 7, 9),
        sort_order=1,
    )

    create_control_group(
        roadmap=roadmap,
        name=CONTROL_GROUP_TEST_NAME_2,
        start_date=datetime.date(2021, 6, 9),
        due_date=datetime.date(2021, 7, 9),
        sort_order=2,
    )

    executed = graphql_client.execute(
        DELETE_GROUP,
        variables={
            'input': {
                'organizationId': graphql_organization.id,
                'id': first_control_group.id,
            }
        },
    )

    control_groups = ControlGroup.objects.all()

    response = executed['data']['deleteControlGroup']['success']
    assert response is True
    assert len(control_groups) == 1
    assert control_groups[0].name == CONTROL_GROUP_TEST_NAME_2
    assert control_groups[0].sort_order == 1


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_control_group_sort_order(graphql_client, graphql_organization):
    roadmap = create_roadmap(
        organization=graphql_organization,
    )

    first_control_group = create_control_group(
        roadmap=roadmap,
        name=CONTROL_GROUP_TEST_NAME_1,
        start_date=datetime.date(2020, 6, 9),
        due_date=datetime.date(2020, 7, 9),
    )

    second_control_group = create_control_group(
        roadmap=roadmap,
        name=CONTROL_GROUP_TEST_NAME_2,
        start_date=datetime.date(2020, 6, 9),
        due_date=datetime.date(2020, 7, 9),
    )

    executed = graphql_client.execute(
        UPDATE_CONTROL_GROUP_SORT_ORDER,
        variables={
            'input': {
                'organizationId': str(graphql_organization.id),
                'controlGroups': [
                    {'id': second_control_group.id, 'sortOrder': 1},
                    {'id': first_control_group.id, 'sortOrder': 2},
                ],
            }
        },
    )

    response = executed['data']['updateControlGroupSortOrder']

    updated_first_sort_order = get_control_group(
        id=first_control_group.id, roadmap=roadmap
    ).sort_order
    updated_second_sort_order = get_control_group(
        id=second_control_group.id, roadmap=roadmap
    ).sort_order

    assert response['success'] is True
    assert updated_first_sort_order == SECOND_PLACE
    assert updated_second_sort_order == FIRST_PLACE


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_control_sort_order(graphql_client, graphql_organization):
    first_control = create_control(
        organization=graphql_organization, name='Control 1', display_id=1
    )

    second_control = create_control(
        organization=graphql_organization, name='Control 2', display_id=2
    )

    executed = graphql_client.execute(
        UPDATE_CONTROL_SORT_ORDER,
        variables={
            'input': {
                'controls': [
                    str(second_control.id),
                    str(first_control.id),
                ]
            }
        },
    )
    response = executed['data']['updateControlSortOrder']

    updated_first_display_id = get_control(
        id=first_control.id, organization=graphql_organization
    ).display_id
    updated_second_display_id = get_control(
        id=second_control.id, organization=graphql_organization
    ).display_id

    assert response['success'] is True
    assert updated_first_display_id == SECOND_PLACE
    assert updated_second_display_id == FIRST_PLACE


@pytest.mark.functional(permissions=['control.add_controlgroup'])
def test_create_control_group(graphql_client, graphql_organization):
    roadmap = create_roadmap(
        organization=graphql_organization,
    )

    first_control_group = create_control_group(
        roadmap=roadmap, name='Control Group test 3'
    )

    second_control_group = create_control_group(
        roadmap=roadmap, name='Control Group test 4'
    )

    executed = graphql_client.execute(
        CREATE_CONTROL_GROUP,
        variables={'input': {'organizationId': str(graphql_organization.id)}},
    )
    response = executed['data']['createControlGroup']['controlGroup']

    updated_first_sort_order = get_control_group(
        id=first_control_group.id, roadmap=roadmap
    ).sort_order
    updated_second_sort_order = get_control_group(
        id=second_control_group.id, roadmap=roadmap
    ).sort_order

    assert response['name'] == 'Untitled Group'
    assert response['referenceId'] == 'XX-01'
    assert response['sortOrder'] == FIRST_PLACE
    assert updated_first_sort_order == SECOND_PLACE
    assert updated_second_sort_order == THIRD_PLACE


@pytest.mark.functional(permissions=['control.add_controlgroup'])
def test_create_control_group_untitled(graphql_client, graphql_organization):
    roadmap = create_roadmap(
        organization=graphql_organization,
    )

    first_control_group = create_control_group(roadmap=roadmap, name='Untitled Group')

    executed = graphql_client.execute(
        CREATE_CONTROL_GROUP,
        variables={'input': {'organizationId': str(graphql_organization.id)}},
    )
    response = executed['data']['createControlGroup']['controlGroup']

    updated_first_sort_order = get_control_group(
        id=first_control_group.id, roadmap=roadmap
    ).sort_order

    assert response['name'] == 'Untitled Group 1'
    assert response['referenceId'] == 'XX-01'
    assert response['sortOrder'] == FIRST_PLACE
    assert updated_first_sort_order == SECOND_PLACE


@pytest.mark.functional(permissions=['control.change_control'])
def test_move_controls_to_control_group(graphql_client, graphql_organization):
    roadmap = create_roadmap(
        organization=graphql_organization,
    )
    first_control_group = create_control_group(
        roadmap=roadmap, name=CONTROL_GROUP_TEST_NAME_1
    )
    second_control_group = create_control_group(
        roadmap=roadmap, name=CONTROL_GROUP_TEST_NAME_2
    )

    first_control = create_control(
        organization=graphql_organization,
        name='Control 1',
        display_id=1,
    )

    second_control = create_control(
        organization=graphql_organization,
        name='Control 2',
        display_id=1,
    )

    first_control.group.set([first_control_group])
    second_control.group.set([second_control_group])

    executed = graphql_client.execute(
        MOVE_CONTROLS_TO_CONTROL_GROUP,
        variables={
            'input': {
                'groupId': int(second_control_group.id),
                'controlIds': [
                    str(first_control.id),
                ],
            }
        },
    )

    ZERO_CONTROLS = 0
    TWO_CONTROLS = 2

    response = executed['data']['moveControlsToControlGroup']
    assert response['success'] is True
    assert first_control.group.all().first() == second_control_group
    assert second_control.group.all().first() == second_control_group
    assert first_control_group.controls.all().count() == ZERO_CONTROLS
    assert second_control_group.controls.all().count() == TWO_CONTROLS
    assert second_control_group.controls.all().filter(id=first_control.id).exists()


def assert_action_items_groups(control_group, expected_start_date, expected_due_date):
    control_group_action_items = ActionItem.objects.filter(
        controls__group=control_group
    ).distinct()
    # Exclude the action item 5 as it is shared
    not_shared_control_group_ais = control_group_action_items.exclude(id=5)
    status_new_query = Q(status=ActionItemStatus.NEW)

    required_control_group_action_items = not_shared_control_group_ais.filter(
        is_required=True
    )
    non_required_control_group_action_items = not_shared_control_group_ais.filter(
        is_required=False
    )
    new_required_control_group_action_items = (
        required_control_group_action_items.filter(status_new_query)
    )
    new_non_required_control_group_action_items = (
        non_required_control_group_action_items.filter(status_new_query)
    )
    completed_required_control_group_action_items = (
        required_control_group_action_items.exclude(status_new_query)
    )
    completed_non_required_control_group_action_items = (
        non_required_control_group_action_items.exclude(status_new_query)
    )

    for action_item in new_required_control_group_action_items:
        assert action_item.start_date == expected_start_date
        assert action_item.due_date == expected_due_date
    for action_item in new_non_required_control_group_action_items:
        assert action_item.due_date != expected_due_date
    for action_item in completed_required_control_group_action_items:
        assert action_item.due_date != expected_due_date
    for action_item in completed_non_required_control_group_action_items:
        assert action_item.due_date != expected_due_date


@pytest.mark.functional(permissions=['control.change_roadmap'])
def test_update_control_group_date_updates_action_items_due_date(
    graphql_client, control_group, _control_group_2, _controls, _action_items
):
    new_start_date = timezone.now() + datetime.timedelta(days=6)
    new_due_date = timezone.now() + datetime.timedelta(days=7)

    (
        action_item_1,
        action_item_2,
        action_item_3,
        action_item_4,
        shared_action_item,
    ) = _action_items
    control_1, control_2, control_3 = _controls

    control_group.controls.add(control_1, control_2)
    _control_group_2.controls.add(control_3)

    control_1.action_items.add(action_item_1, action_item_2, shared_action_item)
    control_2.action_items.add(action_item_3)
    control_3.action_items.add(action_item_4, shared_action_item)

    update_group_input = {
        'input': dict(
            id=control_group.id,
            startDate=new_start_date.isoformat(),
            dueDate=new_due_date.isoformat(),
        )
    }

    graphql_client.execute(UPDATE_CONTROL_GROUP, variables=update_group_input)

    control_group_2 = ControlGroup.objects.get(id=_control_group_2.id)

    control_group_1 = ControlGroup.objects.get(id=control_group.id)
    action_item_1 = ActionItem.objects.get(id=action_item_1.id)
    action_item_2 = ActionItem.objects.get(id=action_item_2.id)
    action_item_3 = ActionItem.objects.get(id=action_item_3.id)
    shared_action_item = ActionItem.objects.get(id=shared_action_item.id)

    assert action_item_1.start_date == control_group_1.start_date
    assert action_item_1.due_date == control_group_1.due_date
    assert action_item_2.start_date != control_group_1.start_date
    assert action_item_2.due_date != control_group_1.due_date
    assert action_item_3.start_date != control_group_1.start_date
    assert action_item_3.due_date != control_group_1.due_date
    assert action_item_4.start_date != new_start_date.replace(tzinfo=pytz.UTC)
    assert action_item_4.due_date != new_due_date.replace(tzinfo=pytz.UTC)

    # The shared action item is group 1 and group 2. Group 1 had an earlier
    # date, but it was changed. Now the group 2 has an earlier date, so check
    # that the shared action item now has the date of the second group
    assert shared_action_item.start_date == control_group_2.start_date
    assert shared_action_item.due_date == control_group_2.due_date

    assert_action_items_groups(
        control_group_1,
        new_start_date.replace(tzinfo=pytz.UTC),
        new_due_date.replace(tzinfo=pytz.UTC),
    )


@pytest.mark.functional(permissions=['control.change_control'])
def test_move_control_to_group_updates_action_items_due_date(
    graphql_client, control_group, _control_group_2, _controls, _action_items
):
    (
        action_item_1,
        action_item_2,
        action_item_3,
        action_item_4,
        shared_action_item,
    ) = _action_items
    control_1, control_2, control_3 = _controls

    control_group.controls.add(control_1)
    _control_group_2.controls.add(control_2, control_3)

    control_1.action_items.add(action_item_3, shared_action_item)
    control_2.action_items.add(action_item_2)
    control_3.action_items.add(action_item_1, action_item_4, shared_action_item)

    graphql_client.execute(
        MOVE_CONTROLS_TO_CONTROL_GROUP,
        variables={
            'input': {
                'groupId': int(control_group.id),
                'controlIds': [
                    str(control_3.id),
                ],
            }
        },
    )

    control_group_1 = ControlGroup.objects.get(id=control_group.id)
    action_item_1 = ActionItem.objects.get(id=action_item_1.id)
    action_item_2 = ActionItem.objects.get(id=action_item_2.id)
    action_item_4 = ActionItem.objects.get(id=action_item_4.id)
    shared_action_item = ActionItem.objects.get(id=shared_action_item.id)

    assert action_item_1.due_date == control_group_1.due_date
    assert action_item_2.due_date != control_group_1.due_date
    assert action_item_4.due_date != control_group_1.due_date

    # Check that the shared action_item has a due date of the first group,
    # as that is from 2020 instead of 2022 for group 2
    assert shared_action_item.due_date == control_group_1.due_date

    assert_action_items_groups(
        control_group_1, control_group_1.start_date, control_group_1.due_date
    )


@pytest.mark.functional()
def test_get_reference_id_for_new_groups(graphql_organization):
    roadmap = RoadMap.objects.create(organization_id=graphql_organization.id)
    ControlGroup.objects.create(roadmap=roadmap, name='New group', reference_id='XX-01')
    ControlGroup.objects.create(
        roadmap=roadmap, name='New group 2', reference_id='XX-02'
    )
    ControlGroup.objects.create(
        roadmap=roadmap, name='New group 3', reference_id='XX-03'
    )

    new_ref = get_reference_id(roadmap)
    assert new_ref == 'XX-04'
    ControlGroup.objects.create(
        roadmap=roadmap, name=f'g-{new_ref}', reference_id=new_ref
    )

    new_ref = get_reference_id(roadmap)
    assert new_ref == 'XX-05'
    ControlGroup.objects.create(
        roadmap=roadmap, name=f'g-{new_ref}', reference_id=new_ref
    )

    new_ref = get_reference_id(roadmap)
    assert new_ref == 'XX-06'
    ControlGroup.objects.create(
        roadmap=roadmap, name=f'g-{new_ref}', reference_id=new_ref
    )
