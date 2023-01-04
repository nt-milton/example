from datetime import datetime

import pytest

from certification.tests.factory import create_certification
from control.constants import CONTROLS_MONITORS_HEALTH
from control.models import Control
from control.tests import (
    GET_CONTROL_DETAILS,
    GET_CONTROL_EVIDENCES,
    GET_CONTROLS_FILTERS,
)
from control.tests.factory import (
    create_action_item,
    create_control,
    create_control_evidence,
    create_control_pillar,
    create_subtask,
    create_system_tag_evidence,
    create_tag,
)
from control.tests.mutations import (
    ADD_CONTROL,
    ADD_CONTROL_EVIDENCE,
    BULK_UPDATE_CONTROL_ACTION_ITEMS,
    DELETE_CONTROL_EVIDENCE,
    DELETE_CONTROLS,
)
from evidence import constants
from evidence.models import Evidence
from feature.models import Flag
from monitor.models import MonitorHealthCondition, MonitorInstanceStatus
from monitor.tests.factory import create_monitor, create_organization_monitor
from tag.tests.functional_tests import create_tags
from user.tests.factory import create_user

TEST_MONITOR_NAME = 'Test Monitor 1'
TEST_MONITOR_NAME_2 = 'Test Monitor 2'
TEST_CONTROL_NAME = 'Test Control 1'
TEST_CONTROL_DESCRIPTION = 'Testing update control'
TEST_QUERY = 'SELECT id, name FROM organization_organization'


def notes_evidence(_id, title, content):
    return {
        "input": {
            "id": _id,
            "laika_paper": {"laikaPaperTitle": title, "laikaPaperContent": content},
            "timeZone": "America/Guayaquil",
        }
    }


def document_evidence(control_id, document_ids):
    return {
        "input": {
            "id": control_id,
            "documents": document_ids,
            "timeZone": "America/Guayaquil",
        }
    }


def add_notes_evidences_response(response):
    return response['data']['addControlEvidence']['evidenceIds']


@pytest.fixture
def controls_with_shared_action_items(graphql_organization, graphql_user):
    first_control = create_control(
        reference_id='AMG-001',
        organization=graphql_organization,
        display_id=1,
        name='Control Test 1',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='<p>testing controls</p>',
    )
    second_control = create_control(
        reference_id='AMG-002',
        organization=graphql_organization,
        display_id=1,
        name='Control Test 2',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='<p>testing controls</p>',
    )

    action_item_1 = create_action_item(
        name='Shared Action Item - 1',
        due_date=None,
        metadata={'referenceId': '00-RE-001'},
    )
    action_item_2 = create_action_item(
        name='Shared Action Item - 2',
        due_date='2022-08-11T18:11:34+00:00',
        metadata={'referenceId': '00-RE-002'},
    )
    action_item_3 = create_action_item(
        name='Shared Action Item - 3',
        due_date='2022-08-09T18:11:34+00:00',
        metadata={'referenceId': 'S-RE-003'},
    )

    first_control.action_items.add(action_item_1, action_item_2, action_item_3)
    second_control.action_items.add(action_item_1, action_item_2, action_item_3)

    action_item_3.assignees.set([graphql_user])

    return first_control, second_control


@pytest.fixture
def controls_with_action_items(graphql_organization, graphql_user):
    first_action_item = create_action_item(
        name='Test Action Item 1 - without owner and dueDate',
        due_date=None,
        metadata={'referenceId': 'AR-RE-001'},
    )

    second_action_item = create_action_item(
        name='Test Action Item - 2',
        due_date='2022-08-09T18:11:34+00:00',
        metadata={'referenceId': 'IR-RE-002'},
    )

    third_action_item = create_action_item(name='Test Action Item - 3')

    second_action_item.assignees.add(graphql_user)

    first_control = create_control(
        reference_id='AMG-001',
        organization=graphql_organization,
        display_id=1,
        name='Control Test 1',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='<p>testing controls</p>',
    )

    first_control.action_items.add(first_action_item, second_action_item)

    second_control = create_control(
        reference_id='AMG-002',
        organization=graphql_organization,
        display_id=1,
        name='Control Test 2',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='<p>testing controls</p>',
    )

    second_control.action_items.add(first_action_item, second_action_item)

    third_control = create_control(
        reference_id='AMG-003',
        organization=graphql_organization,
        display_id=1,
        name='Control Test 3',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='<p>testing controls</p>',
    )

    third_control.action_items.add(third_action_item)

    return [first_control, second_control, third_control]


@pytest.mark.functional(permissions=['control.change_control'])
def test_update_control_notes(graphql_client, graphql_organization):
    control = create_control(
        reference_id='AMG-001',
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='<p>testing controls</p>',
    )
    variables = {
        'input': {
            'id': str(control.id),
            'implementationNotes': '<p>controls notes tested</p>',
        }
    }

    response = graphql_client.execute(
        '''
            mutation updateControlNotes($input: UpdateControlInput!) {
                updateControl(input: $input) {
                  data {
                    id
                    implementationNotes
                  }
                }
            }
        ''',
        variables=variables,
    )
    data = dict(response['data']['updateControl']['data'])
    notes = data['implementationNotes']
    assert notes == '<p>controls notes tested</p>'


def get_health_variables(id):
    return {
        'id': str(id),
    }


def set_up_test(graphql_client, graphql_organization, monitor_1, monitor_2):
    control = create_control(
        reference_id='AMG-001',
        organization=graphql_organization,
        display_id=1,
        name=TEST_CONTROL_NAME,
        description=TEST_CONTROL_DESCRIPTION,
    )
    monitor = create_monitor(
        name=TEST_MONITOR_NAME,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )

    monitor2 = create_monitor(
        name=TEST_MONITOR_NAME_2,
        query=TEST_QUERY,
        health_condition=MonitorHealthCondition.EMPTY_RESULTS,
    )

    create_organization_monitor(
        graphql_organization,
        monitor,
        status=monitor_1['status'],
        active=monitor_1['active'],
    )

    create_organization_monitor(
        graphql_organization,
        monitor2,
        status=monitor_2['status'],
        active=monitor_2['active'],
    )

    monitor.control_references = control.name
    monitor2.control_references = control.name
    monitor.save()
    monitor2.save()
    response = graphql_client.execute(
        GET_CONTROL_DETAILS, variables=get_health_variables(control.id)
    )
    return response


@pytest.mark.functional(permissions=['control.view_control'])
@pytest.mark.parametrize(
    (
        'monitor_status_1',
        'monitor_active_1',
        'monitor_status_2',
        'monitor_active_2',
        'health',
        'flagged',
    ),
    [
        (
            MonitorInstanceStatus.NO_DATA_DETECTED,
            False,
            MonitorInstanceStatus.NO_DATA_DETECTED,
            False,
            CONTROLS_MONITORS_HEALTH['NO_MONITORS'],
            0,
        ),
        (
            MonitorInstanceStatus.NO_DATA_DETECTED,
            True,
            MonitorInstanceStatus.NO_DATA_DETECTED,
            True,
            CONTROLS_MONITORS_HEALTH['NO_DATA'],
            0,
        ),
        (
            MonitorInstanceStatus.NO_DATA_DETECTED,
            True,
            MonitorInstanceStatus.HEALTHY,
            True,
            CONTROLS_MONITORS_HEALTH['NO_DATA'],
            0,
        ),
        (
            MonitorInstanceStatus.TRIGGERED,
            True,
            MonitorInstanceStatus.NO_DATA_DETECTED,
            True,
            CONTROLS_MONITORS_HEALTH['FLAGGED'],
            1,
        ),
        (
            MonitorInstanceStatus.HEALTHY,
            True,
            MonitorInstanceStatus.NO_DATA_DETECTED,
            False,
            CONTROLS_MONITORS_HEALTH['HEALTHY'],
            0,
        ),
        (
            MonitorInstanceStatus.HEALTHY,
            True,
            MonitorInstanceStatus.HEALTHY,
            True,
            CONTROLS_MONITORS_HEALTH['HEALTHY'],
            0,
        ),
    ],
)
def test_health_monitors(
    monitor_status_1,
    monitor_active_1,
    monitor_status_2,
    monitor_active_2,
    health,
    flagged,
    graphql_client,
    graphql_organization,
):
    flag = Flag.objects.filter(
        name='newControlsFeatureFlag', organization=graphql_organization
    )
    if flag:
        flag.delete()

    monitor_1 = {'status': monitor_status_1, 'active': monitor_active_1}
    monitor_2 = {'status': monitor_status_2, 'active': monitor_active_2}
    response = set_up_test(graphql_client, graphql_organization, monitor_1, monitor_2)

    health = response['data']['control']['health']
    flagged_monitors = response['data']['control']['flaggedMonitors']
    assert health == health
    assert flagged_monitors == flagged


@pytest.mark.functional(permissions=['control.view_control'])
def test_navigation_info_control_query(graphql_client, graphql_organization):
    GET_CONTROL_NAVIGATION_INFO = '''
        query getControlDetails($id: UUID!) {
            control(id: $id) {
                previous
                next
            }
        }
    '''
    control: Control = None
    reference_ids = ['AX-001', 'AZ-002', 'AR-003', 'AO-004', 'AP-005']
    for id in range(10):
        new_control = create_control(
            organization=graphql_organization,
            name='Control test {id}',
            display_id=id + 1,
            reference_id=reference_ids[id] if id < 5 else None,
        )
        if id == 2:
            control = new_control
    response = graphql_client.execute(
        GET_CONTROL_NAVIGATION_INFO, variables=get_health_variables(control.id)
    )
    navigation_info = response['data']['control']
    assert response.get('errors') is None
    assert navigation_info['previous'] == str(control.previous.id)
    assert navigation_info['next'] == str(control.next.id)


def get_control_evidences_response_collection(response):
    return response['data']['controlEvidence']['data']


@pytest.mark.functional(permissions=['control.view_control'])
def test_control_evidences_query(graphql_client, graphql_organization):
    control = create_control(
        reference_id='AMG-001',
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='',
    )
    control_evidence = create_control_evidence(
        control=control,
        name='Evidence Test',
        organization=graphql_organization,
        description='',
    )

    executed = graphql_client.execute(
        GET_CONTROL_EVIDENCES,
        variables={'id': str(control.id), 'pagination': dict(page=1, pageSize=10)},
    )

    collection = get_control_evidences_response_collection(executed)
    first_result, *_ = collection
    assert int(first_result['id']) == control_evidence.id


def link_tags_to_organization(tags, control):
    for t in tags:
        t.controls.add(control)


def get_filter_group_items(response):
    filter_group_items = {}
    for filter_group in response['data']['controlsFilters']['data']:
        items_list = []
        for item in filter_group['items']:
            items_list.append(item['name'])
        filter_group_items[filter_group['category']] = items_list
    return filter_group_items


def get_controls_filters_response(graphql_client):
    response = graphql_client.execute(GET_CONTROLS_FILTERS)
    return get_filter_group_items(response)


@pytest.mark.functional(permissions=['control.view_control'])
def test_controls_filters_status(graphql_client):
    filter_group_items = get_controls_filters_response(graphql_client)

    assert filter_group_items['STATUS'][0].upper() == 'IMPLEMENTED'
    assert filter_group_items['STATUS'][1].upper() == 'NOT IMPLEMENTED'


@pytest.mark.functional(permissions=['control.view_control'])
def test_controls_filters_health(graphql_client):
    filter_group_items = get_controls_filters_response(graphql_client)

    assert filter_group_items['HEALTH'][0].upper() == 'NEEDS ATTENTION'
    assert filter_group_items['HEALTH'][1].upper() == 'OPERATIONAL'


@pytest.mark.functional(permissions=['control.view_control'])
def test_controls_filters_framework(graphql_client, graphql_organization):
    soc2_sections = ['CC1.1', 'CC2.2']
    soc2_certificate = create_certification(
        graphql_organization,
        soc2_sections,
        name='SOC 2 Type 2',
        unlock_certificate=True,
    )
    filter_group_items = get_controls_filters_response(graphql_client)

    assert filter_group_items['FRAMEWORK'][0] == soc2_certificate.name


@pytest.mark.functional(permissions=['control.view_control'])
def test_controls_filters_pillar(graphql_client, graphql_organization):
    control = create_control(
        reference_id='AMG-001',
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
    )
    pillar = create_control_pillar('HR Governance')
    pillar.control.add(control)
    filter_group_items = get_controls_filters_response(graphql_client)

    assert filter_group_items['CONTROL FAMILY'][0] == pillar.name


@pytest.mark.functional(permissions=['control.view_control'])
def test_controls_filters_tags(graphql_client, graphql_organization):
    control = create_control(
        reference_id='AMG-001',
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
    )
    tags = create_tags(graphql_organization)
    link_tags_to_organization(tags, control)
    filter_group_items = get_controls_filters_response(graphql_client)

    assert filter_group_items['TAGS'][0] == tags[0].name
    assert filter_group_items['TAGS'][1] == tags[1].name


@pytest.mark.functional(permissions=['control.add_control'])
def test_create_control_with_pillar(graphql_client):
    pillar = create_control_pillar('My Pillar')
    form_values = {
        'name': 'My Control',
        'description': 'The control description here',
        'pillarId': pillar.id,
        'tagNames': [],
        'ownerEmails': [],
        'certificationSectionIds': [],
    }
    response = graphql_client.execute(ADD_CONTROL, variables={'input': form_values})
    control_id = response['data']['createControl']['data']['id']
    control: Control = Control.objects.get(id=control_id)
    assert response.get('errors', None) is None
    assert control.name == form_values['name']
    assert control.description == form_values['description']
    assert control.tags.count() == 0
    assert len(control.owners) == 0
    assert control.pillar.id == form_values['pillarId']


@pytest.mark.functional(permissions=['control.add_control'])
def test_create_control_with_empty_spaces_in_name_description(graphql_client):
    pillar = create_control_pillar('My Pillar')
    form_values = {
        'reference_id': 'AMG-001',
        'name': '   ',
        'description': '   ',
        'pillarId': pillar.id,
        'tagNames': [],
        'ownerEmails': [],
        'certificationSectionIds': [],
    }
    response = graphql_client.execute(ADD_CONTROL, variables={'input': form_values})
    assert response.get('errors', None) is not None
    assert response['errors'][0]['message'] is not None


@pytest.mark.functional(permissions=['control.delete_control_evidence'])
def test_delete_control_evidences_query(graphql_client, graphql_organization):
    control = create_control(
        reference_id='AMG-001',
        organization=graphql_organization,
        display_id=1,
        name='Control Test',
        description=TEST_CONTROL_DESCRIPTION,
        implementation_notes='',
    )
    control_evidence = create_control_evidence(
        control=control,
        name='Evidence Test',
        organization=graphql_organization,
        description='',
    )
    subtask = create_subtask(organization=graphql_organization, name='Subtask evidence')
    tag = create_tag(name=subtask.id, organization=graphql_organization)
    create_system_tag_evidence(tag=tag, evidence=control_evidence)

    input_values = {
        'evidence': '[{"id":"%d"}]' % control_evidence.id,
        'id': str(control.id),
    }

    response = graphql_client.execute(
        DELETE_CONTROL_EVIDENCE, variables={'input': input_values}
    )

    deleted = response['data']['deleteControlEvidence']['deleted']
    assert response.get('errors', None) is None
    assert deleted is None


@pytest.mark.functional(
    permissions=['control.batch_delete_control', 'control.batch_delete_control']
)
def test_delete_controls(
    graphql_client, graphql_organization, controls_with_action_items
):
    first_control, second_control, _ = controls_with_action_items
    executed = graphql_client.execute(
        DELETE_CONTROLS,
        variables={
            "input": {
                "ids": [str(first_control.id), str(second_control.id)],
                "organizationId": str(graphql_organization.id),
            }
        },
    )

    controls = graphql_organization.controls.all()

    REMAINING_ACTION_ITEMS = 1
    REMAINING_CONTROLS = 1

    for control in controls:
        action_items = control.action_items.all()
        assert len(action_items) == REMAINING_ACTION_ITEMS

    response = executed['data']['deleteControls']['success']
    assert response is True
    assert len(controls) == REMAINING_CONTROLS


@pytest.mark.functional(permissions=['control.add_control_evidence'])
def test_attachment_evidences_add_notes(graphql_client, graphql_organization):
    control = create_control(
        organization=graphql_organization, display_id=1, name='test control'
    )

    note_title = "Sample note"
    note_content = "<p>This is a sample content...</p>"

    executed = graphql_client.execute(
        ADD_CONTROL_EVIDENCE,
        variables=notes_evidence(str(control.id), note_title, note_content),
    )

    evidence_ids = add_notes_evidences_response(executed)

    evidence = Evidence.objects.get(id=evidence_ids[0])

    assert evidence.type == constants.LAIKA_PAPER
    assert evidence.name == f'{note_title}.laikapaper'
    assert evidence.evidence_text == note_content


@pytest.mark.functional(permissions=['control.add_control_evidence'])
def test_control_add_duplicated__document(graphql_client, graphql_organization):
    control = create_control(
        organization=graphql_organization, display_id=1, name='Test control'
    )

    evidence = Evidence.objects.create(
        name='Test evidence',
        description='fake description',
        type='FILE',
        organization=graphql_organization,
    )

    response = graphql_client.execute(
        ADD_CONTROL_EVIDENCE,
        variables=document_evidence(str(control.id), [str(evidence.id)]),
    )

    addControlEvidence = response['data']['addControlEvidence']
    evidence_ids = addControlEvidence['evidenceIds']
    duplicated_ids = addControlEvidence['duplicatedIds']

    assert evidence_ids[0] == str(evidence.id)
    assert len(duplicated_ids) == 0

    duplicated = graphql_client.execute(
        ADD_CONTROL_EVIDENCE,
        variables=document_evidence(str(control.id), [str(evidence.id)]),
    )

    addControlEvidence = duplicated['data']['addControlEvidence']
    duplicated_ids = addControlEvidence['duplicatedIds']

    assert duplicated_ids[0] == str(evidence.id)


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_bulk_update_action_item_due_date(graphql_client, controls_with_action_items):
    _, control_2, _ = controls_with_action_items

    new_due_date = '2022-08-10T18:11:34+00:00'

    graphql_client.execute(
        BULK_UPDATE_CONTROL_ACTION_ITEMS,
        variables={
            'input': {
                'controlId': str(control_2.id),
                'dueDate': new_due_date,
            }
        },
    )

    control_2_action_items = control_2.action_items.all()

    assert control_2_action_items[0].due_date == datetime.strptime(
        new_due_date, '%Y-%m-%dT%H:%M:%S%z'
    )


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_bulk_update_action_item_due_date_for_shared_action_items(
    graphql_client, controls_with_shared_action_items
):
    first_control, _ = controls_with_shared_action_items

    new_due_date = '2022-08-10T18:11:34+00:00'

    # Shouldn't change the dueDate for the shared action item
    # which dueDate is soonest to expire in comparison to the dueDate
    # provided as input
    action_item_closest_to_expire = (
        first_control.action_items.all()
        .exclude(due_date=None)
        .order_by('due_date')
        .first()
    )

    first_control_action_items = first_control.action_items.all().order_by('due_date')[
        1:
    ]

    graphql_client.execute(
        BULK_UPDATE_CONTROL_ACTION_ITEMS,
        variables={
            'input': {
                'controlId': str(first_control.id),
                'dueDate': new_due_date,
            }
        },
    )

    assert first_control_action_items[0].due_date == datetime.strptime(
        new_due_date, '%Y-%m-%dT%H:%M:%S%z'
    )
    assert first_control_action_items[1].due_date == datetime.strptime(
        new_due_date, '%Y-%m-%dT%H:%M:%S%z'
    )
    assert action_item_closest_to_expire.due_date != datetime.strptime(
        new_due_date, '%Y-%m-%dT%H:%M:%S%z'
    )


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_bulk_update_action_item_with_empty_values(
    graphql_client, controls_with_shared_action_items, graphql_user
):
    first_control, _ = controls_with_shared_action_items
    graphql_client.execute(
        BULK_UPDATE_CONTROL_ACTION_ITEMS,
        variables={
            'input': {'controlId': str(first_control.id), 'dueDate': None, 'owner': ''}
        },
    )

    first_control_action_items = first_control.action_items.all()

    action_item_without_due_date_and_owner = first_control_action_items.get(
        name='Shared Action Item - 1'
    )
    action_item_without_owner_1 = first_control_action_items.get(
        name='Shared Action Item - 2'
    )
    action_item_with_owner_1 = first_control_action_items.get(
        name='Shared Action Item - 3'
    )

    assert action_item_without_due_date_and_owner.due_date is None
    assert action_item_without_due_date_and_owner.assignees.first() is None
    assert action_item_without_owner_1.due_date is not None
    assert action_item_without_owner_1.assignees.first() is None
    assert action_item_with_owner_1.due_date is not None
    assert action_item_with_owner_1.assignees.first().email != ''


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_bulk_update_all_action_items_owner(
    graphql_client, graphql_user, controls_with_action_items
):
    first_control, _, _ = controls_with_action_items
    graphql_client.execute(
        BULK_UPDATE_CONTROL_ACTION_ITEMS,
        variables={
            'input': {
                'controlId': str(first_control.id),
                'owner': graphql_user.email,
                'overwriteAll': True,
            }
        },
    )
    first_control_action_items = first_control.action_items.all()

    assert first_control_action_items[0].assignees.first().email == graphql_user.email
    assert first_control_action_items[1].assignees.first().email == graphql_user.email


@pytest.mark.functional(permissions=['action_item.change_actionitem'])
def test_bulk_update_action_items_without_owner(
    graphql_client, graphql_organization, controls_with_action_items
):
    new_user = create_user(graphql_organization, email='jose+test@heylaika.com')
    first_control, _, _ = controls_with_action_items
    graphql_client.execute(
        BULK_UPDATE_CONTROL_ACTION_ITEMS,
        variables={
            'input': {
                'controlId': str(first_control.id),
                'owner': new_user.email,
                'overwriteAll': False,
            }
        },
    )

    action_item_without_owner = first_control.action_items.filter(
        assignees__email=new_user.email
    ).first()

    assert (
        action_item_without_owner.name
        == 'Test Action Item 1 - without owner and dueDate'
    )
    assert action_item_without_owner.assignees.first().email == new_user.email
