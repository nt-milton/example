import datetime

import pytest

from control.tests import create_control
from control.tests.factory import create_action_item
from control.tests.queries import GET_CONTROL_ACTION_ITEMS

today_date = datetime.date.today()
tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)


@pytest.fixture(name="_action_items")
def fixture_action_items():
    action_items_dict_list = [
        {
            "name": "00-S-001_with_first_display_id",
            "description": "AI with display_id",
            "display_id": 2,
            "status": "new",
            "is_required": True,
            "is_recurrent": False,
            "due_date": today_date,
            "metadata": {
                'isCustom': False,
                'referenceId': '00-S-001',
                'requiredEvidence': '',
            },
        },
        {
            "name": "00-S-012_with_second_display_id",
            "description": "AI with display_id",
            "display_id": 4,
            "status": "new",
            "is_required": True,
            "is_recurrent": False,
            "due_date": today_date,
            "metadata": {
                'isCustom': False,
                'referenceId': '00-S-012',
                'requiredEvidence': 'Yes',
            },
        },
        {
            "name": "PI-R-021_required",
            "description": "AI required with no display_id",
            "status": "new",
            "is_required": True,
            "is_recurrent": True,
            "due_date": today_date,
            "metadata": {
                'referenceId': 'PI-R-021',
                'requiredEvidence': 'No',
            },
        },
        {
            "name": "00-S-002_not_required",
            "description": "AI not required with no display_id and custom",
            "status": "new",
            "is_required": False,
            "is_recurrent": False,
            "due_date": today_date,
            "metadata": {'isCustom': True, 'referenceId': 'F0-S-002'},
        },
        {
            "name": "PI-R-001_custom",
            "description": "Custom action item",
            "status": "new",
            "is_required": False,
            "is_recurrent": True,
            "due_date": today_date,
            "metadata": {'isCustom': True, 'referenceId': 'PI-R-001'},
        },
        {
            "name": "PI-R-012_not_custom",
            "description": "Not custom action item and ref id",
            "status": "new",
            "is_required": False,
            "is_recurrent": True,
            "due_date": today_date,
            "metadata": {
                'referenceId': 'OI-R-012',
            },
        },
        {
            "name": "00-S-003_recurrent",
            "description": "Recurrent action item and ref id",
            "status": "new",
            "is_required": False,
            "is_recurrent": True,
            "due_date": today_date,
            "metadata": {'referenceId': 'PS-003'},
        },
        {
            "name": "PI-R-002_not_recurrent",
            "description": "Not Recurrent action item and ref id",
            "status": "new",
            "is_required": False,
            "is_recurrent": False,
            "due_date": today_date,
            "metadata": {'referenceId': 'QI-R-002'},
        },
        {
            "name": "PI-R-011_first_due_date",
            "description": "AI sorted by due date and ref id",
            "status": "new",
            "is_required": False,
            "is_recurrent": False,
            "due_date": today_date,
            "metadata": {'referenceId': 'RI-R-011'},
        },
        {
            "name": "00-P-001_second_due_date",
            "description": "AI sorted by due date",
            "status": "completed",
            "is_required": False,
            "is_recurrent": False,
            "due_date": tomorrow_date,
            "metadata": {'referenceId': '00-P-001'},
        },
    ]

    return [create_action_item(**action_item) for action_item in action_items_dict_list]


@pytest.fixture(name="_control_1")
def fixture_control(graphql_organization, _action_items):
    control = create_control(
        organization=graphql_organization,
        display_id=1,
        reference_id="AMG-001",
        name='Control Test 1',
        description='Control with action items',
        implementation_notes='',
    )
    control.action_items.add(*_action_items)
    return control


@pytest.mark.functional(permissions=['action_item.view_actionitem'])
def test_action_items_are_sorted(graphql_client, _control_1):
    response = graphql_client.execute(
        GET_CONTROL_ACTION_ITEMS, variables={'id': str(_control_1.id)}
    )

    expected_action_item_names = [
        "00-S-001_with_first_display_id",
        "00-S-012_with_second_display_id",
        "PI-R-021_required",
        "00-S-002_not_required",
        "PI-R-001_custom",
        "PI-R-012_not_custom",
        "00-S-003_recurrent",
        "PI-R-002_not_recurrent",
        "PI-R-011_first_due_date",
        "00-P-001_second_due_date",
    ]
    actual_action_item_names = [
        action_item['name'] for action_item in response['data']['controlActionItems']
    ]

    assert actual_action_item_names == expected_action_item_names
