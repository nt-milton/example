import json
from copy import deepcopy

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q
from django.utils.timezone import now

from access_review.models import AccessReviewPreference
from access_review.mutations import RECURRENT_ACTION_ITEM
from action_item.models import ActionItem
from blueprint.models import EvidenceMetadataBlueprint
from control.constants import CONTROL_TYPE, MetadataFields
from control.tasks import FrequencyMapping
from control.tests import GET_CONTROL_DETAILS, create_control
from control.tests.factory import create_action_item
from control.tests.functional_tests import TEST_CONTROL_DESCRIPTION
from control.tests.mutations import (
    ADD_CONTROL_ACTION_ITEM,
    DELETE_CONTROLS,
    UPDATE_CONTROL_ACTION_ITEM,
)
from control.tests.queries import GET_CONTROL_ACTION_ITEMS
from user.models import User


@pytest.fixture(autouse=True)
def set_up_test(graphql_user, _control, _action_item):
    _control.action_items.add(_action_item)
    _action_item.assignees.add(graphql_user)


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


@pytest.fixture(name="_control_1")
def fixture_control_1(graphql_organization):
    return create_control(
        organization=graphql_organization,
        reference_id="AMG-002",
        display_id=2,
        name='Control Test 2',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='',
    )


@pytest.fixture(name="_action_item")
def fixture_action_item():
    return create_action_item(
        name='LAI-001',
        description='Action item description',
        completion_date=now(),
        status='new',
        due_date=now(),
        is_required=False,
        is_recurrent=False,
        recurrent_schedule='monthly',
        metadata={'isCustom': True, 'type': 'control'},
    )


@pytest.fixture(name="_action_item_for_access_review")
def fixture_action_item_for_access_review(graphql_organization, _action_item):
    _action_item.name = RECURRENT_ACTION_ITEM
    _action_item.metadata = {
        'organizationId': str(graphql_organization.id),
        'referenceId': RECURRENT_ACTION_ITEM,
        'isCustom': True,
    }
    _action_item.save()
    return _action_item


@pytest.fixture(name="_children_action_items")
def fixture_children_action_items(_action_item):
    action_item_child_1 = deepcopy(_action_item)
    action_item_child_1.id = None
    action_item_child_1.parent_action_item_id = _action_item.id
    action_item_child_1.save()

    action_item_child_2 = deepcopy(_action_item)
    action_item_child_2.id = None
    action_item_child_2.parent_action_item_id = _action_item.id
    action_item_child_2.save()

    return action_item_child_1, action_item_child_2


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_update_control_action_item_for_access_review(
    graphql_client,
    graphql_organization,
    graphql_user,
    _control,
    _action_item_for_access_review,
):
    access_review_preference = AccessReviewPreference.objects.create(
        organization=graphql_organization
    )

    input_values = {
        'actionItemId': _action_item_for_access_review.id,
        'completionDate': None,
        'dueDate': '2021-10-13T18:11:34+00:00',
        'isRecurrent': True,
        'owner': graphql_user.email,
        'status': 'completed',
        'recurrentSchedule': 'weekly',
    }

    graphql_client.execute(
        UPDATE_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )

    _action_item_for_access_review.refresh_from_db()
    access_review_preference.refresh_from_db()

    assert _action_item_for_access_review.due_date == access_review_preference.due_date


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_update_control_action_item(
    graphql_client,
    graphql_organization,
    graphql_user,
    _control,
    _action_item,
):
    # When
    input_values = {
        'actionItemId': _action_item.id,
        'completionDate': None,
        'dueDate': '2021-10-13T18:11:34+00:00',
        'isRecurrent': True,
        'owner': graphql_user.email,
        'status': 'completed',
        'recurrentSchedule': 'weekly',
    }

    response = graphql_client.execute(
        UPDATE_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )

    # Then
    item_resp = response['data']['updateControlActionItem']['actionItem']

    assert input_values['actionItemId'] == int(item_resp['id'])
    assert input_values['dueDate'] == item_resp['dueDate']
    assert input_values['isRecurrent'] == bool(item_resp['isRecurrent'])
    assert input_values['status'] == item_resp['status']
    assert input_values['recurrentSchedule'] == item_resp['recurrentSchedule']
    assert input_values['owner'] == item_resp['owner']['email']
    assert input_values['completionDate'] is None
    assert User.objects.get(email=graphql_user.email)


@pytest.mark.functional(permissions=['action_item.view_actionitem'])
def test_failed_update_control_action_item_with_wrong_permissions(
    graphql_client, graphql_organization, graphql_user, _control, _action_item, caplog
):
    # When
    input_values = {
        'actionItemId': _action_item.id,
        'dueDate': '2021-10-13T18:11:34+00:00',
        'isRecurrent': False,
        'owner': graphql_user.email,
        'status': 'new',
        'recurrentSchedule': 'monthly',
    }

    graphql_client.execute(
        UPDATE_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )

    # Then
    for log_output in [
        "Failed to update a control action item",
        "PermissionDenied",
        "Mutation.updateControlActionItem",
    ]:
        assert log_output in caplog.text


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_failed_update_with_wrong_status_choice(
    graphql_client, graphql_organization, graphql_user, _control, _action_item, caplog
):
    # When
    input_values = {
        'actionItemId': _action_item.id,
        'dueDate': '2021-10-13T18:11:34+00:00',
        'isRecurrent': False,
        'owner': graphql_user.email,
        'status': 'INVALID_STATUS',
        'recurrentSchedule': 'monthly',
    }

    graphql_client.execute(
        UPDATE_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )

    # Then
    assert "Value 'INVALID_STATUS' is not a valid choice" in caplog.text


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_failed_update_with_empty_description(
    graphql_client, graphql_organization, graphql_user, _control, _action_item
):
    # When
    input_values = {'actionItemId': _action_item.id, 'description': ''}

    response = graphql_client.execute(
        UPDATE_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )
    message = response['errors'][0]['message']
    assert 'Failed to update a control action item.' in message


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_update_description_on_parent_for_related_action_items(
    graphql_client,
    graphql_organization,
    graphql_user,
    _control,
    _action_item,
    _children_action_items,
):
    # When
    input_values = {
        'actionItemId': _action_item.id,
        'description': 'new description for parent and children ai',
    }

    response = graphql_client.execute(
        UPDATE_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )

    # Then
    action_item_child_1, action_item_child_2 = ActionItem.objects.filter(
        parent_action_item__id=input_values['actionItemId']
    )

    item_resp = response['data']['updateControlActionItem']['actionItem']

    assert input_values['actionItemId'] == int(item_resp['id'])
    assert input_values['description'] == item_resp['description']
    assert input_values['description'] == action_item_child_1.description
    assert input_values['description'] == action_item_child_2.description


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_update_description_on_child_for_related_action_items(
    graphql_client,
    graphql_organization,
    graphql_user,
    _control,
    _action_item,
    _children_action_items,
):
    # When
    action_item_child_1, action_item_child_2 = _children_action_items

    input_values = {
        'actionItemId': action_item_child_1.id,
        'description': 'new description for parent and children ai',
    }

    response = graphql_client.execute(
        UPDATE_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )

    # Then
    action_item_1, action_item_2, action_item_3 = ActionItem.objects.filter(
        Q(pk=action_item_child_1.parent_action_item.id)
        | Q(parent_action_item_id=action_item_child_1.parent_action_item.id)
    )

    item_resp = response['data']['updateControlActionItem']['actionItem']

    assert input_values['actionItemId'] == int(item_resp['id'])
    assert input_values['description'] == item_resp['description']
    assert input_values['description'] == action_item_1.description
    assert input_values['description'] == action_item_2.description
    assert input_values['description'] == action_item_3.description


@pytest.mark.functional(permissions=['action_item.add_actionitem'])
@pytest.mark.parametrize(
    'frequency', [freq.value.name for freq in FrequencyMapping if bool(freq.value.name)]
)
def test_add_control_action_item_with_frequency(
    graphql_client, graphql_organization, graphql_user, _control, frequency
):
    # When
    input_values = {
        'name': 'RAI-001',
        'description': '',
        'isRequired': True,
        'recurrentSchedule': frequency,
        'dueDate': '2021-10-13T18:11:34+00:00',
        'owner': graphql_user.email,
        'controlId': _control.id,
        'metadata': '{"requiredEvidence": true}',
    }

    response = graphql_client.execute(
        ADD_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )

    # Then
    _validate_created_action_item('XX-C-001', 'RAI-001', True, input_values, response)


@pytest.mark.functional(permissions=['action_item.add_actionitem'])
def test_add_control_action_item_onetime_frequency(
    graphql_client,
    graphql_organization,
    graphql_user,
    _control,
):
    # When
    input_values = {
        'name': 'CAI-001',
        'description': '',
        'isRequired': True,
        'recurrentSchedule': '',
        'dueDate': '2021-10-13T18:11:34+00:00',
        'owner': graphql_user.email,
        'controlId': _control.id,
        'metadata': '{"requiredEvidence": true}',
    }

    response = graphql_client.execute(
        ADD_CONTROL_ACTION_ITEM, variables={'input': input_values}
    )

    metadata = json.loads(input_values['metadata'])
    metadata[MetadataFields.IS_CUSTOM.value] = True
    # Then
    _validate_created_action_item('XX-C-001', 'CAI-001', False, input_values, response)


def _validate_created_action_item(
    reference_id, action_item_name, is_recurrent, input_values, response
):
    item_resp = response['data']['addControlActionItem']['actionItem']

    assert action_item_name == item_resp['name']
    assert input_values['dueDate'] == item_resp['dueDate']
    assert is_recurrent == item_resp['isRecurrent']
    assert input_values['isRequired'] == item_resp['isRequired']
    assert input_values['recurrentSchedule'] == item_resp['recurrentSchedule']
    assert input_values['owner'] == item_resp['owner']['email']
    assert User.objects.get(email=input_values['owner'])

    metadata = json.loads(item_resp['metadata'])
    assert metadata[MetadataFields.IS_CUSTOM.value]
    assert metadata[MetadataFields.REQUIRED_EVIDENCE.value]
    assert metadata[MetadataFields.TYPE.value] == CONTROL_TYPE
    assert metadata[MetadataFields.REFERENCE_ID.value] == reference_id


@pytest.mark.functional(permissions=['control.view_control'])
def test_all_control_action_items_have_no_assignees(
    graphql_client, graphql_organization, _control
):
    response = graphql_client.execute(
        GET_CONTROL_DETAILS, variables={'id': str(_control.id)}
    )

    assert response['data']['control']['allActionItemsHaveNoAssignees'] is False


@pytest.mark.functional(permissions=['control.batch_delete_control'])
def test_delete_control_does_not_delete_shared_action_items(
    graphql_client, graphql_organization, _action_item, _control, _control_1
):
    _control.action_items.add(_action_item)
    _control_1.action_items.add(_action_item)

    graphql_client.execute(
        DELETE_CONTROLS,
        variables={
            "input": {
                "ids": [str(_control.id)],
                "organizationId": str(graphql_organization.id),
            }
        },
    )

    assert ActionItem.objects.count() == 1
    assert _control_1.action_items.first().name == "LAI-001"


@pytest.mark.functional(permissions=['action_item.view_actionitem'])
def test_action_items_evidence_metadata(
    graphql_client, graphql_organization, _action_item, _control
):
    _action_item.metadata['referenceId'] = _control.reference_id
    _action_item.save()
    attachment_name = 'some_file_name.pdf'
    attachment = SimpleUploadedFile(attachment_name, b'Test pdf file')
    EvidenceMetadataBlueprint.objects.create(
        reference_id=_control.reference_id, name='evidence1', attachment=attachment
    )
    _control.action_items.add(_action_item)
    response = graphql_client.execute(
        GET_CONTROL_ACTION_ITEMS, variables={'id': str(_control.id)}
    )
    evidence = response['data']['controlActionItems'][0]['evidenceMetadata']
    assert evidence['referenceId'] == _control.reference_id
    assert evidence['attachment']['name'] == attachment_name
