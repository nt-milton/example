import base64
import logging
from datetime import datetime

import pytest

from action_item.models import ActionItem
from action_item.tests.factory import create_action_item_evidence
from action_item.tests.functional_tests import _create_action_items
from action_item.tests.mutations import (
    ADD_ACTION_ITEM_EVIDENCE,
    DELETE_ACTION_ITEM_EVIDENCE,
)
from action_item.tests.queries import GET_ACTION_ITEM_EVIDENCES
from control.tests.factory import create_control
from evidence import constants
from evidence.models import Evidence
from tag.tests.functional_tests import create_tags
from user.tests import create_user

logger = logging.getLogger('action_item_evidence_handler')


@pytest.fixture
def users(graphql_organization):
    return [create_user(graphql_organization, [], 'johndoe@heylaika.com')]


def get_action_item_evidences_response_collection(response):
    return response['data']['actionItemEvidences']


@pytest.mark.functional()
def test_action_item_evidences_query(graphql_client, graphql_organization, users):
    action_item = _create_action_items(users)[0]
    action_item_evidence = create_action_item_evidence(
        action_item=action_item,
        name='Evidence Test',
        organization=graphql_organization,
        description='',
    )

    executed = graphql_client.execute(
        GET_ACTION_ITEM_EVIDENCES, variables={'id': str(action_item.id)}
    )

    collection = get_action_item_evidences_response_collection(executed)
    first_result, *_ = collection
    assert int(first_result['id']) == action_item_evidence.id


def add_action_item_evidences_response(response):
    return response['data']['addActionItemEvidence']['evidenceIds']


def link_tags_to_control(tags, control):
    for t in tags:
        t.controls.add(control)


def get_evidence_form_values(id):
    file_content = base64.b64encode('Drive file'.encode())

    return {
        'files': [{'fileName': 'some_file_name.txt', 'file': file_content}],
        'id': id,
        'timeZone': 'America/New_York',
        'documents': [],
        'officers': [],
        'otherEvidence': [],
        'policies': [],
        'teams': [],
    }


def notes_evidence(_id, title, content):
    return {
        "input": {
            "id": _id,
            "laika_paper": {"laikaPaperTitle": title, "laikaPaperContent": content},
        }
    }


@pytest.mark.functional(permissions=['action_item.view_actionitem'])
def test_action_item_evidences_tags(graphql_client, graphql_organization, users):
    control = create_control(
        organization=graphql_organization, display_id=1, name='test control'
    )

    tags = create_tags(graphql_organization)
    link_tags_to_control(tags, control)

    data = {
        'name': 'test action item',
        'description': 'description',
        'due_date': datetime.today(),
        'users': users,
    }
    action_item = ActionItem.objects.create_action_items(**data)
    action_item[0].controls.add(control)

    executed = graphql_client.execute(
        ADD_ACTION_ITEM_EVIDENCE,
        variables={'input': get_evidence_form_values(action_item[0].id)},
    )

    evidenceIds = add_action_item_evidences_response(executed)

    evidence = Evidence.objects.get(id=evidenceIds[0])

    tag_names = [tag.name for tag in evidence.tags.all()]

    for tag in tags:
        assert tag.name in tag_names

    assert len(evidence.tags.all()) == 2


@pytest.mark.functional(permissions=['action_item.view_actionitem'])
def test_action_item_evidences_delete(graphql_client, graphql_organization, users):
    action_item = _create_action_items(users)
    evidence = create_action_item_evidence(
        action_item=action_item[0],
        name='Evidence Test',
        organization=graphql_organization,
        description='',
    )

    evidence_id = evidence.id
    input = {
        'input': {
            'id': action_item[0].id,
            'evidence': '[{"id":' + str(evidence_id) + '}]',
        }
    }
    graphql_client.execute(DELETE_ACTION_ITEM_EVIDENCE, variables=input)

    deleted_evidence_relation = Evidence.objects.filter(
        id=evidence_id, action_items=action_item[0]
    )
    assert not deleted_evidence_relation.exists()

    undeleted_evidence = Evidence.objects.filter(id=evidence_id)

    assert undeleted_evidence.exists()


@pytest.mark.functional(permissions=['action_item.view_actionitem'])
def test_action_item_evidences_add_notes(graphql_client, graphql_organization, users):
    data = {
        'name': 'test action item',
        'description': 'description',
        'due_date': datetime.today(),
        'users': users,
    }
    control = create_control(
        organization=graphql_organization, display_id=1, name='test control'
    )
    action_item = ActionItem.objects.create_action_items(**data)
    action_item[0].controls.add(control)

    note_title = "Sample note"
    note_content = "<p>This is a sample content...</p>"

    executed = graphql_client.execute(
        ADD_ACTION_ITEM_EVIDENCE,
        variables=notes_evidence(action_item[0].id, note_title, note_content),
    )

    evidence_ids = add_action_item_evidences_response(executed)

    evidence = Evidence.objects.get(id=evidence_ids[0])

    assert evidence.type == constants.LAIKA_PAPER
    assert evidence.name == note_title
    assert evidence.evidence_text == note_content
