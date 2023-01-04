import datetime

import pytest

from access_review.mutations import RECURRENT_ACTION_ITEM as ac_recurrent_action_item
from access_review.utils import ACCESS_REVIEW_TYPE
from action_item.models import ActionItemStatus
from control.tests import create_control
from control.tests.factory import create_action_item
from control.tests.queries import GET_CONTROL_ACTION_ITEMS
from control.utils.factory import BGC_ACTION_ITEM_CODE
from feature.constants import background_check_feature_flag
from objects.utils import BACKGROUND_CHECK_TYPE


@pytest.mark.functional(
    permissions=['action_item.view_actionitem'],
    feature_flags=[background_check_feature_flag],
)
@pytest.mark.parametrize(
    'referenceId, type_key,',
    [
        (ac_recurrent_action_item, ACCESS_REVIEW_TYPE),
        (BGC_ACTION_ITEM_CODE, BACKGROUND_CHECK_TYPE),
    ],
)
def test_action_items_tray(graphql_client, graphql_organization, referenceId, type_key):
    control = create_control(
        organization=graphql_organization,
        display_id=1,
        reference_id="AMG-001",
        name='Control Test 1',
        description='Control with action items',
        implementation_notes='',
    )
    action_item = create_action_item(
        name="Action item 2",
        description="Action item description 1",
        status=ActionItemStatus.NEW,
        is_required=True,
        is_recurrent=False,
        due_date=datetime.date.today(),
        metadata={
            'referenceId': referenceId,
            'organizationId': str(graphql_organization.id),
        },
    )
    control.action_items.add(action_item)
    response = graphql_client.execute(
        GET_CONTROL_ACTION_ITEMS, variables={'id': str(control.id)}
    )

    assert response['data']['controlActionItems'][0]['trayData']['typeKey'] == type_key


@pytest.mark.functional(permissions=['action_item.view_actionitem'])
def test_action_items_tray_no_reference_id_match(graphql_client, graphql_organization):
    control = create_control(
        organization=graphql_organization,
        display_id=1,
        reference_id="AMG-001",
        name='Control Test 1',
        description='Control with action items',
        implementation_notes='',
    )
    action_item = create_action_item(
        name="Action item 2",
        description="Action item description 1",
        status=ActionItemStatus.NEW,
        is_required=True,
        is_recurrent=False,
        due_date=datetime.date.today(),
        metadata={
            'referenceId': 'test',
            'organizationId': str(graphql_organization.id),
        },
    )
    control.action_items.add(action_item)
    response = graphql_client.execute(
        GET_CONTROL_ACTION_ITEMS, variables={'id': str(control.id)}
    )
    assert response['data']['controlActionItems'][0]['trayData'] is None
